"""Views module for the sensor data application."""

from datetime import UTC

from django.conf import settings
from django.db import connections
from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .ingestion import ingest_dealiot_sensor_event
from .models import WildFiDecodedSensorEvent
from .serializers import WildFiSensorBatchSerializer


def health_live(request):
    """Return a cheap liveness response."""
    del request
    return JsonResponse({"status": "ok", "service": "sensor"})


def health_ready(request):
    """Return readiness after checking the default database connection."""
    del request
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse(
            {
                "status": "error",
                "service": "sensor",
                "database": "unavailable",
                "detail": str(exc),
            },
            status=503,
        )
    return JsonResponse(
        {"status": "ok", "service": "sensor", "database": "available"},
    )


def metrics(request):
    """Return minimal Prometheus metrics for the sensor service."""
    del request
    total_events = WildFiDecodedSensorEvent.objects.count()
    total_devices = (
        WildFiDecodedSensorEvent.objects.values("wildfi_device_id")
        .distinct()
        .count()
    )
    body = "\n".join(
        [
            "# HELP dealdata_sensor_wildfi_events_total Stored WildFi sensor events.",
            "# TYPE dealdata_sensor_wildfi_events_total gauge",
            f"dealdata_sensor_wildfi_events_total {total_events}",
            "# HELP dealdata_sensor_wildfi_devices_total WildFi sensor devices.",
            "# TYPE dealdata_sensor_wildfi_devices_total gauge",
            f"dealdata_sensor_wildfi_devices_total {total_devices}",
            "",
        ],
    )
    return HttpResponse(body, content_type="text/plain; version=0.0.4")


def _token_error(request) -> Response | None:
    token = getattr(settings, "DEALDATA_INGEST_TOKEN", "")
    if not token:
        return None
    if request.headers.get("X-DEALDATA-INGEST-TOKEN") == token:
        return None
    return Response(
        {"detail": "Invalid ingestion token."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _serialize_sensor_event(event: WildFiDecodedSensorEvent) -> dict[str, object]:
    return {
        "id": str(event.wildfi_decoded_sensor_event_id),
        "device_id": event.wildfi_device_id,
        "observed_object_id": (
            str(event.observed_object_id) if event.observed_object_id else None
        ),
        "event_id": event.event_id,
        "payload_hash": event.payload_hash,
        "topic": event.dealiot_topic,
        "source": event.source,
        "mqtt_topic": event.mqtt_topic,
        "timestamp": event.acquisition_time.isoformat(),
        "ingested_at": event.ingested_at.isoformat() if event.ingested_at else None,
        "sensor_type": event.sensor_type,
        "payload": event.payload,
        "metadata": event.message_metadata,
    }


def _parse_positive_int(value: str | None, default: int, maximum: int) -> int:
    if value in (None, ""):
        return default
    parsed = int(value)
    if parsed < 0:
        raise ValueError("Expected a positive integer.")
    return min(parsed, maximum)


def _parse_datetime_filter(value: str | None, field_name: str):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        message = f"Query parameter '{field_name}' must be an ISO datetime."
        raise ValueError(message)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


class WildFiSensorIngestView(APIView):
    """Receive decoded WildFi sensor events from DEALIoT."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    def post(self, request) -> Response:
        """Persist one decoded DEALIoT `raw.sensor` event idempotently."""
        token_error = _token_error(request)
        if token_error:
            return token_error

        if not isinstance(request.data, dict):
            return Response(
                {"detail": "Expected a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        body, response_status = ingest_dealiot_sensor_event(request.data)
        return Response(body, status=response_status)


class WildFiSensorListView(APIView):
    """List stored WildFi sensor events."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    def get(self, request) -> Response:
        """Return sensor events filtered by device, type, source, topic and time."""
        try:
            limit = _parse_positive_int(
                request.query_params.get("limit"),
                default=100,
                maximum=1000,
            )
            offset = _parse_positive_int(
                request.query_params.get("offset"),
                default=0,
                maximum=1_000_000,
            )
            started_at = _parse_datetime_filter(
                request.query_params.get("from"),
                "from",
            )
            ended_at = _parse_datetime_filter(
                request.query_params.get("to"),
                "to",
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = WildFiDecodedSensorEvent.objects.order_by(
            "-acquisition_time",
            "-created_at",
        )
        device_id = request.query_params.get("device_id")
        if device_id:
            queryset = queryset.filter(wildfi_device_id=device_id)
        sensor_type = request.query_params.get("sensor_type")
        if sensor_type:
            queryset = queryset.filter(sensor_type=sensor_type)
        source = request.query_params.get("source")
        if source:
            queryset = queryset.filter(source=source)
        topic = request.query_params.get("topic")
        if topic:
            queryset = queryset.filter(dealiot_topic=topic)
        if started_at:
            queryset = queryset.filter(acquisition_time__gte=started_at)
        if ended_at:
            queryset = queryset.filter(acquisition_time__lte=ended_at)

        total = queryset.count()
        rows = queryset[offset : offset + limit]
        return Response(
            {
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": [_serialize_sensor_event(row) for row in rows],
            },
        )


class WildFiSensorBatchIngestView(APIView):
    """Receive a batch of decoded WildFi sensor events from DEALIoT."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    def post(self, request) -> Response:
        """Persist decoded DEALIoT `raw.sensor` events idempotently."""
        token_error = _token_error(request)
        if token_error:
            return token_error

        data = request.data
        if isinstance(data, list):
            data = {"events": data}
        if not isinstance(data, dict):
            return Response(
                {"detail": "Expected a JSON object or array."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WildFiSensorBatchSerializer(data=data)
        if not serializer.is_valid():
            return Response(
                {"detail": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        inserted = 0
        duplicates = 0
        errors = 0
        for index, event_payload in enumerate(serializer.validated_data["events"]):
            body, response_status = ingest_dealiot_sensor_event(event_payload)
            result = {"index": index, "status": response_status, **body}
            results.append(result)
            if response_status == status.HTTP_201_CREATED:
                inserted += 1
            elif response_status == status.HTTP_200_OK and body.get("duplicate"):
                duplicates += 1
            else:
                errors += 1

        return Response(
            {
                "inserted": inserted,
                "duplicates": duplicates,
                "errors": errors,
                "results": results,
            },
            status=status.HTTP_200_OK if errors == 0 else status.HTTP_207_MULTI_STATUS,
        )
