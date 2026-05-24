"""Views module for the sensor data application."""

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, connections, transaction
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WildFiDecodedSensorEvent
from .serializers import (
    WildFiSensorBatchSerializer,
    WildFiSensorIngestSerializer,
)


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


def _find_existing(
    event: WildFiDecodedSensorEvent,
) -> WildFiDecodedSensorEvent | None:
    if event.event_id:
        existing = WildFiDecodedSensorEvent.objects.filter(
            source=event.source,
            event_id=event.event_id,
        ).first()
        if existing:
            return existing
    if event.payload_hash:
        return WildFiDecodedSensorEvent.objects.filter(
            source=event.source,
            payload_hash=event.payload_hash,
        ).first()
    return None


def _serialize_event(
    event: WildFiDecodedSensorEvent,
    *,
    duplicate: bool,
) -> dict[str, object]:
    return {
        "id": str(event.wildfi_decoded_sensor_event_id),
        "duplicate": duplicate,
        "device_id": event.wildfi_device_id,
        "event_id": event.event_id,
        "payload_hash": event.payload_hash,
        "topic": event.dealiot_topic,
        "timestamp": event.acquisition_time.isoformat(),
        "sensor_type": event.sensor_type,
    }


def _ingest_event(payload: dict[str, object]) -> tuple[dict[str, object], int]:
    serializer = WildFiSensorIngestSerializer(data=payload)
    if not serializer.is_valid():
        return {"detail": serializer.errors}, status.HTTP_400_BAD_REQUEST

    event = WildFiDecodedSensorEvent.from_dealiot_event(serializer.validated_data)
    existing = _find_existing(event)
    if existing:
        return _serialize_event(existing, duplicate=True), status.HTTP_200_OK

    try:
        with transaction.atomic():
            event.full_clean()
            event.save()
    except DjangoValidationError as exc:
        return {"detail": exc.message_dict}, status.HTTP_400_BAD_REQUEST
    except IntegrityError:
        existing = _find_existing(event)
        if existing:
            return _serialize_event(existing, duplicate=True), status.HTTP_200_OK
        raise

    return _serialize_event(event, duplicate=False), status.HTTP_201_CREATED


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

        body, response_status = _ingest_event(request.data)
        return Response(body, status=response_status)


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
            body, response_status = _ingest_event(event_payload)
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
