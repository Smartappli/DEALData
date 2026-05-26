"""Ingestion helpers for decoded DEALIoT sensor events."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import status

from .models import WildFiDecodedSensorEvent
from .serializers import WildFiSensorIngestSerializer


def find_existing_sensor_event(
        event: WildFiDecodedSensorEvent,
) -> WildFiDecodedSensorEvent | None:
    """Return an already-ingested event matching idempotency keys."""
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


def serialize_sensor_ingest_event(
        event: WildFiDecodedSensorEvent,
        *,
        duplicate: bool,
) -> dict[str, object]:
    """Return the compact ingestion response for a sensor event."""
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


def ingest_dealiot_sensor_event(
        payload: dict[str, object],
) -> tuple[dict[str, object], int]:
    """Persist one decoded DEALIoT `raw.sensor` event idempotently."""
    serializer = WildFiSensorIngestSerializer(data=payload)
    if not serializer.is_valid():
        return {"detail": serializer.errors}, status.HTTP_400_BAD_REQUEST

    event = WildFiDecodedSensorEvent.from_dealiot_event(serializer.validated_data)
    existing = find_existing_sensor_event(event)
    if existing:
        return (
            serialize_sensor_ingest_event(existing, duplicate=True),
            status.HTTP_200_OK,
        )

    try:
        with transaction.atomic():
            event.full_clean()
            event.save()
    except DjangoValidationError as exc:
        return {"detail": exc.message_dict}, status.HTTP_400_BAD_REQUEST
    except IntegrityError:
        existing = find_existing_sensor_event(event)
        if existing:
            return (
                serialize_sensor_ingest_event(existing, duplicate=True),
                status.HTTP_200_OK,
            )
        raise

    return (
        serialize_sensor_ingest_event(event, duplicate=False),
        status.HTTP_201_CREATED,
    )
