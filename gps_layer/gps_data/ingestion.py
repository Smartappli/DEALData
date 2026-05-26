"""Ingestion helpers for decoded DEALIoT GPS events."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import status

from .models import WildFiGPSFix
from .serializers import WildFiGPSIngestSerializer


def find_existing_gps_event(event: WildFiGPSFix) -> WildFiGPSFix | None:
    """Return an already-ingested event matching idempotency keys."""
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


def serialize_gps_ingest_event(
        event: WildFiGPSFix,
        *,
        duplicate: bool,
) -> dict[str, object]:
    """Return the compact ingestion response for a GPS event."""
    return {
        "id": str(event.wildfi_gps_fix_id),
        "duplicate": duplicate,
        "device_id": event.wildfi_device_id,
        "event_id": event.event_id,
        "payload_hash": event.payload_hash,
        "topic": event.dealiot_topic,
        "timestamp": event.acquisition_time.isoformat(),
    }


def ingest_dealiot_gps_event(
        payload: dict[str, object],
) -> tuple[dict[str, object], int]:
    """Persist one decoded DEALIoT `raw.gps` event idempotently."""
    serializer = WildFiGPSIngestSerializer(data=payload)
    if not serializer.is_valid():
        return {"detail": serializer.errors}, status.HTTP_400_BAD_REQUEST

    event = WildFiGPSFix.from_dealiot_event(serializer.validated_data)
    existing = find_existing_gps_event(event)
    if existing:
        return (
            serialize_gps_ingest_event(existing, duplicate=True),
            status.HTTP_200_OK,
        )

    try:
        with transaction.atomic():
            event.full_clean()
            event.save()
    except DjangoValidationError as exc:
        return {"detail": exc.message_dict}, status.HTTP_400_BAD_REQUEST
    except IntegrityError:
        existing = find_existing_gps_event(event)
        if existing:
            return (
                serialize_gps_ingest_event(existing, duplicate=True),
                status.HTTP_200_OK,
            )
        raise

    return serialize_gps_ingest_event(event, duplicate=False), status.HTTP_201_CREATED
