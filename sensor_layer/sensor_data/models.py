"""Data models for the sensor layer."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any, ClassVar

from django.db import models
from django.db.models import F
from django.utils.dateparse import parse_datetime
from uuid_utils import uuid7


def _parse_event_datetime(value: Any, field_name: str) -> datetime:
    """Parse an ISO datetime from a DEALIoT event."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_datetime(value)
    else:
        parsed = None

    if parsed is None:
        message = f"DEALIoT event field '{field_name}' must be an ISO datetime."
        raise ValueError(message)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _parse_optional_event_datetime(value: Any, field_name: str) -> datetime | None:
    """Parse an optional ISO datetime from a DEALIoT event."""
    if value in (None, ""):
        return None
    return _parse_event_datetime(value, field_name)


def _payload_dict(value: Any) -> dict[str, Any]:
    """Keep decoded payloads queryable while preserving scalar values."""
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    return {"value": value}


def _event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    """Keep transport metadata from MQTT/Kafka without shaping it too early."""
    metadata_fields = ("qos", "retain", "partition", "offset", "key")
    return {field: event[field] for field in metadata_fields if field in event}


def _stable_event_hash(event: dict[str, Any]) -> str:
    """Build a stable idempotency hash for a decoded DEALIoT event."""
    serialized = json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class Sensor(models.Model):
    """Physical sensor metadata."""

    sensor_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    sensor_vendor = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        verbose_name="Vendor",
        help_text="Bosch",
    )
    sensor_model = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        verbose_name="Model",
        help_text="BMP 680",
    )
    sensor_code = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        verbose_name="Sensor Code",
        help_text="Sensor n°1",
    )
    sensor_create_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    sensor_update_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    class Meta:
        """Model metadata for sensors."""

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["sensor_code"],
                name="uq_sensor_code",
            ),
        ]

    def __str__(self) -> str:
        """Return the sensor code."""
        return self.sensor_code


class SensorObservedObject(models.Model):
    """Association between a sensor and an observed object."""

    sensor_observed_object_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    sensor_observed_object_object_id = models.UUIDField(
        verbose_name="Observed Object ID",
        help_text="UUID of the observed object managed by the core layer.",
    )
    sensor_observed_object_sensor = models.ForeignKey(
        Sensor,
        on_delete=models.CASCADE,
        related_name="sensor_observed_object_sensor",
    )
    sensor_observed_object_start_time = models.TimeField()
    sensor_observed_object_end_time = models.TimeField()
    sensor_observed_object_notes = models.CharField(max_length=255)
    sensor_observed_object_create_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    sensor_observed_object_update_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    class Meta:
        """Model metadata for sensor-observed object links."""

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(
                    sensor_observed_object_end_time__gte=F(
                        "sensor_observed_object_start_time",
                    ),
                ),
                name="soo_end_time_gte_start_time",
            ),
        ]

    def __str__(self) -> str:
        """Return the linked sensor code."""
        return self.sensor_observed_object_sensor.sensor_code


class SensorData(models.Model):
    """Raw sensor measurements."""

    sensor_data_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    sensor_data_sensor = models.ForeignKey(
        Sensor,
        on_delete=models.CASCADE,
        related_name="sensor_data_sensor",
    )
    sensor_data_utc_date = models.DateField()
    sensor_data_utc_time = models.TimeField()
    sensor_data_lmt_date = models.DateField()
    sensor_data_lmt_time = models.TimeField()
    sensor_data_value = models.JSONField(default=dict)
    sensor_data_create_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    sensor_data_update_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    def __str__(self) -> str:
        """Return the sensor data value as a string."""
        return str(self.sensor_data_value)


class WildFiDecodedSensorEvent(models.Model):
    """Decoded WildFi sensor event received from DEALIoT."""

    wildfi_decoded_sensor_event_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    wildfi_device_id = models.CharField(max_length=128, db_index=True)
    event_id = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="Optional upstream DEALIoT/Kafka event identifier.",
    )
    message_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional Kafka or MQTT key used by DEALIoT.",
    )
    payload_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Stable SHA-256 hash used for idempotent ingestion.",
    )
    observed_object_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="Observed Object ID",
        help_text="UUID of the observed object managed by the core layer.",
    )
    dealiot_topic = models.CharField(
        max_length=64,
        default="raw.sensor",
        db_index=True,
    )
    source = models.CharField(max_length=64, default="wildfi-mqtt")
    mqtt_topic = models.CharField(max_length=255, blank=True)
    acquisition_time = models.DateTimeField(db_index=True)
    ingested_at = models.DateTimeField(null=True, blank=True)
    sensor_type = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    message_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata for decoded WildFi sensor events."""

        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["wildfi_device_id", "acquisition_time"]),
            models.Index(fields=["dealiot_topic", "acquisition_time"]),
            models.Index(fields=["sensor_type", "acquisition_time"]),
        ]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["source", "event_id"],
                condition=~models.Q(event_id=""),
                name="uq_wildfi_sensor_source_event_id",
            ),
            models.UniqueConstraint(
                fields=["source", "payload_hash"],
                condition=~models.Q(payload_hash=""),
                name="uq_wildfi_sensor_source_payload_hash",
            ),
        ]

    @classmethod
    def from_dealiot_event(
        cls,
        event: dict[str, Any],
        *,
        topic: str = "raw.sensor",
    ) -> "WildFiDecodedSensorEvent":
        """Build a sensor event from the decoded DEALIoT `raw.sensor` contract."""
        payload = _payload_dict(event.get("payload"))
        device_id = event.get("device_id") or payload.get("device_id")
        if not device_id:
            message = "DEALIoT sensor event must contain 'device_id'."
            raise ValueError(message)

        sensor_type = (
            event.get("sensor_type")
            or payload.get("sensor_type")
            or payload.get("type")
            or ""
        )

        return cls(
            wildfi_device_id=str(device_id),
            event_id=str(event.get("event_id") or event.get("id") or ""),
            message_key=str(event.get("key") or ""),
            payload_hash=_stable_event_hash(event),
            dealiot_topic=str(event.get("topic") or topic),
            source=str(event.get("source") or "wildfi-mqtt"),
            mqtt_topic=str(event.get("mqtt_topic") or ""),
            acquisition_time=_parse_event_datetime(
                event.get("timestamp"),
                "timestamp",
            ),
            ingested_at=_parse_optional_event_datetime(
                event.get("ingested_at"),
                "ingested_at",
            ),
            sensor_type=str(sensor_type),
            payload=payload,
            message_metadata=_event_metadata(event),
        )

    def save(self, *args, **kwargs):
        """Ensure directly-created events still have an idempotency hash."""
        if not self.payload_hash:
            payload = {
                "device_id": self.wildfi_device_id,
                "timestamp": self.acquisition_time,
                "topic": self.dealiot_topic,
                "source": self.source,
                "mqtt_topic": self.mqtt_topic,
                "sensor_type": self.sensor_type,
                "payload": self.payload,
            }
            self.payload_hash = _stable_event_hash(payload)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return a readable device and timestamp pair."""
        return f"{self.wildfi_device_id} @ {self.acquisition_time.isoformat()}"


class SensorDataObservedObject(models.Model):
    """Sensor data attached to a specific observed object."""

    sensor_data_observed_object_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    sensor_data_observed_object_sensor = models.ForeignKey(
        Sensor,
        on_delete=models.CASCADE,
        related_name="sensor_data_observed_object_sensor",
    )
    sensor_data_observed_object_object_id = models.UUIDField(
        verbose_name="Observed Object ID",
        help_text="UUID of the observed object managed by the core layer.",
    )
    sensor_data_observed_object_acquisition_time = models.DateTimeField()
    sensor_data_observed_object_value = models.JSONField(
        default=dict,
    )
    sensor_data_observed_object_create_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    sensor_data_observed_object_update_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )

    def __str__(self) -> str:
        """Return the observed-object sensor data value as a string."""
        return str(self.sensor_data_observed_object_value)
