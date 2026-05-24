"""Views for the gps_data application."""

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WildFiGPSFix


def health_live(request):
    """Return a cheap liveness response."""
    del request
    return JsonResponse({"status": "ok", "service": "gps"})


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


def _find_existing(event: WildFiGPSFix) -> WildFiGPSFix | None:
    if event.event_id:
        existing = WildFiGPSFix.objects.filter(
            source=event.source,
            event_id=event.event_id,
        ).first()
        if existing:
            return existing
    if event.payload_hash:
        return WildFiGPSFix.objects.filter(
            source=event.source,
            payload_hash=event.payload_hash,
        ).first()
    return None


def _serialize_event(event: WildFiGPSFix, *, duplicate: bool) -> dict[str, object]:
    return {
        "id": str(event.wildfi_gps_fix_id),
        "duplicate": duplicate,
        "device_id": event.wildfi_device_id,
        "event_id": event.event_id,
        "payload_hash": event.payload_hash,
        "topic": event.dealiot_topic,
        "timestamp": event.acquisition_time.isoformat(),
    }


class WildFiGPSIngestView(APIView):
    """Receive decoded WildFi GPS events from DEALIoT."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    def post(self, request) -> Response:
        """Persist one decoded DEALIoT `raw.gps` event idempotently."""
        token_error = _token_error(request)
        if token_error:
            return token_error

        try:
            event = WildFiGPSFix.from_dealiot_event(request.data)
        except (TypeError, ValueError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = _find_existing(event)
        if existing:
            return Response(_serialize_event(existing, duplicate=True))

        try:
            with transaction.atomic():
                event.full_clean()
                event.save()
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.message_dict},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            existing = _find_existing(event)
            if existing:
                return Response(_serialize_event(existing, duplicate=True))
            raise

        return Response(
            _serialize_event(event, duplicate=False),
            status=status.HTTP_201_CREATED,
        )
