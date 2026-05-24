"""Data models for the GPS layer."""

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


def _event_float(
    event: dict[str, Any],
    payload: dict[str, Any],
    *field_names: str,
    required: bool = False,
) -> float | None:
    """Extract a float from top-level DEALIoT fields or decoded payload."""
    for field_name in field_names:
        value = event.get(field_name)
        if value in (None, ""):
            value = payload.get(field_name)
        if value not in (None, ""):
            return float(value)
    if required:
        names = ", ".join(field_names)
        message = f"DEALIoT event must contain one of: {names}."
        raise ValueError(message)
    return None


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


class GPSSensor(models.Model):
    """GPS sensor metadata and configuration."""

    gps_sensors_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    gps_sensors_code = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="GPS Sensors Code of Identification",
        help_text="e.g.: Ulg GPS 12",
    )
    gps_sensor_purchase_date = models.DateField(
        verbose_name="GPS Sensor Purchase Date",
        help_text="e.g.: 2020-07-07",
    )
    gps_sensor_frequency = models.FloatField(
        verbose_name="GPS Sensor Sampling Rate (Hz)",
        help_text="e.g.: 60",
    )
    gps_sensor_vendor = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="GPS Sensor Vendor Name",
        help_text="e.g.: Globaltek",
    )
    gps_sensor_model = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="GPS Sensor Model",
        help_text="e.g.: FT203",
    )
    gps_sensor_sim_card = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="IEMI Card Number",
        help_text="e.g.: 123454564654651654",
    )
    gps_sensor_active = models.BooleanField(
        default=True,
        verbose_name="GPS Sensor Status",
        help_text="GPS Sensor Status",
    )
    gps_sensor_created_at = models.DateTimeField(auto_now_add=True)
    gps_sensor_updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return the sensor code."""
        return self.gps_sensors_code


class ObservedObjectGPSSensor(models.Model):
    """Link an observed object to a GPS sensor over a time interval."""

    observed_object_gps_sensors_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    observed_object_gps_sensor_observed_object_id = models.UUIDField(
        verbose_name="Observed Object ID",
        help_text="UUID of the observed object managed by the core layer.",
    )
    observed_object_gps_sensor_gps_sensor = models.ForeignKey(
        GPSSensor,
        on_delete=models.CASCADE,
        related_name="gps_sensor_link",
    )
    observed_object_start_time = models.DateTimeField()
    observed_object_end_time = models.DateTimeField()
    observed_object_notes = models.JSONField(
        default=dict,
        verbose_name="GPS Sensor Notes",
        help_text='e.g.: {"type_of_data": "GPS Data Imported from file"}',
    )

    class Meta:
        """Model metadata for observed object and GPS sensor links."""

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(
                    observed_object_start_time__lte=F(
                        "observed_object_end_time",
                    ),
                ),
                name="ck_timestamp_start_before_end",
            ),
            models.UniqueConstraint(
                fields=[
                    "observed_object_gps_sensor_observed_object_id",
                    "observed_object_gps_sensor_gps_sensor",
                    "observed_object_start_time",
                ],
                name="uq_obj_sensor_start",
            ),
        ]


class GPSRawData(models.Model):
    """Raw GPS data points imported from acquisition files."""

    gps_raw_data_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    gps_raw_data_sensors_code = models.CharField(max_length=64)
    gps_raw_data_line_no = models.IntegerField()
    gps_raw_data_utc_date = models.DateField()
    gps_raw_data_utc_time = models.TimeField()
    gps_raw_data_lmt_date = models.DateField()
    gps_raw_data_lmt_time = models.TimeField()
    gps_raw_data_ecef_x = models.IntegerField()
    gps_raw_data_ecef_y = models.IntegerField()
    gps_raw_data_ecef_z = models.IntegerField()
    gps_raw_data_latitude = models.FloatField()
    gps_raw_data_longitude = models.FloatField()
    gps_raw_data_height = models.FloatField()
    gps_raw_data_dop = models.FloatField()
    gps_raw_data_nav = models.CharField(max_length=2)
    gps_raw_data_validated = models.CharField(max_length=3)
    gps_raw_data_sats_used = models.IntegerField()
    gps_raw_data_ch01_sat_id = models.IntegerField()
    gps_raw_data_ch01_sat_cnr = models.IntegerField()
    gps_raw_data_ch02_sat_id = models.IntegerField()
    gps_raw_data_ch02_sat_cnr = models.IntegerField()
    gps_raw_data_ch03_sat_id = models.IntegerField()
    gps_raw_data_ch03_sat_cnr = models.IntegerField()
    gps_raw_data_ch04_sat_id = models.IntegerField()
    gps_raw_data_ch04_sat_cnr = models.IntegerField()
    gps_raw_data_ch05_sat_id = models.IntegerField()
    gps_raw_data_ch05_sat_cnr = models.IntegerField()
    gps_raw_data_ch06_sat_id = models.IntegerField()
    gps_raw_data_ch06_sat_cnr = models.IntegerField()
    gps_raw_data_ch07_sat_id = models.IntegerField()
    gps_raw_data_ch07_sat_cnr = models.IntegerField()
    gps_raw_data_ch08_sat_id = models.IntegerField()
    gps_raw_data_ch08_sat_cnr = models.IntegerField()
    gps_raw_data_ch09_sat_id = models.IntegerField()
    gps_raw_data_ch09_sat_cnr = models.IntegerField()
    gps_raw_data_ch10_sat_id = models.IntegerField()
    gps_raw_data_ch10_sat_cnr = models.IntegerField()
    gps_raw_data_ch11_sat_id = models.IntegerField()
    gps_raw_data_ch11_sat_cnr = models.IntegerField()
    gps_raw_data_ch12_sat_id = models.IntegerField()
    gps_raw_data_ch12_sat_cnr = models.IntegerField()
    gps_raw_data_main_vol = models.FloatField()
    gps_raw_data_bu_vol = models.FloatField()
    gps_raw_data_temp = models.FloatField()
    gps_raw_data_easting = models.IntegerField()
    gps_raw_data_northing = models.IntegerField()
    gps_raw_data_remarks = models.TextField()
    gps_raw_data_created_at = models.DateTimeField(auto_now_add=True)
    gps_raw_data_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata for raw GPS data."""

        db_table = "gps_raw_data"


class WildFiGPSFix(models.Model):
    """Decoded WildFi GPS event received from DEALIoT."""

    wildfi_gps_fix_id = models.UUIDField(
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
        default="raw.gps",
        db_index=True,
    )
    source = models.CharField(max_length=64, default="wildfi-mqtt")
    mqtt_topic = models.CharField(max_length=255, blank=True)
    acquisition_time = models.DateTimeField(db_index=True)
    ingested_at = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    altitude = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    message_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata for decoded WildFi GPS fixes."""

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=(
                    models.Q(latitude__gte=-90.0)
                    & models.Q(latitude__lte=90.0)
                ),
                name="ck_wildfi_gps_latitude_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(longitude__gte=-180.0)
                    & models.Q(longitude__lte=180.0)
                ),
                name="ck_wildfi_gps_longitude_range",
            ),
            models.UniqueConstraint(
                fields=["source", "event_id"],
                condition=~models.Q(event_id=""),
                name="uq_wildfi_gps_source_event_id",
            ),
            models.UniqueConstraint(
                fields=["source", "payload_hash"],
                condition=~models.Q(payload_hash=""),
                name="uq_wildfi_gps_source_payload_hash",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["wildfi_device_id", "acquisition_time"]),
            models.Index(fields=["dealiot_topic", "acquisition_time"]),
        ]

    @classmethod
    def from_dealiot_event(
        cls,
        event: dict[str, Any],
        *,
        topic: str = "raw.gps",
    ) -> "WildFiGPSFix":
        """Build a GPS fix from the decoded DEALIoT `raw.gps` contract."""
        payload = _payload_dict(event.get("payload"))
        device_id = event.get("device_id") or payload.get("device_id")
        if not device_id:
            message = "DEALIoT GPS event must contain 'device_id'."
            raise ValueError(message)

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
            latitude=_event_float(
                event,
                payload,
                "latitude",
                "lat",
                required=True,
            ),
            longitude=_event_float(
                event,
                payload,
                "longitude",
                "lon",
                "lng",
                required=True,
            ),
            altitude=_event_float(event, payload, "altitude", "alt"),
            speed=_event_float(event, payload, "speed"),
            heading=_event_float(event, payload, "heading", "course"),
            payload=payload,
            message_metadata=_event_metadata(event),
        )

    def as_geojson(self) -> dict[str, Any]:
        """Return the GPS fix as a GeoJSON point."""
        return {
            "type": "Point",
            "coordinates": [self.longitude, self.latitude],
        }

    def save(self, *args, **kwargs):
        """Ensure directly-created events still have an idempotency hash."""
        if not self.payload_hash:
            payload = {
                "device_id": self.wildfi_device_id,
                "timestamp": self.acquisition_time,
                "topic": self.dealiot_topic,
                "source": self.source,
                "mqtt_topic": self.mqtt_topic,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "altitude": self.altitude,
                "speed": self.speed,
                "heading": self.heading,
                "payload": self.payload,
            }
            self.payload_hash = _stable_event_hash(payload)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return a readable device and timestamp pair."""
        return f"{self.wildfi_device_id} @ {self.acquisition_time.isoformat()}"


class ProcessedGPSDataObservedObject(models.Model):
    """Processed GPS positions associated with an observed object."""

    processed_gps_data_observed_object_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )
    processed_gps_data_sensors = models.ForeignKey(
        GPSSensor,
        on_delete=models.CASCADE,
        related_name="gps_sensor_link2",
    )
    processed_gps_data_observed_object_uuid = models.UUIDField(
        verbose_name="Observed Object ID",
        help_text="UUID of the observed object managed by the core layer.",
    )
    processed_gps_data_observed_object_acquisition_time = models.DateTimeField()
    processed_gps_data_observed_object_longitude = models.FloatField()
    processed_gps_data_observed_object_latitude = models.FloatField()
    processed_gps_data_observed_object_geom = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Processed GPS Geometry",
        help_text="GeoJSON point in EPSG:4326.",
    )
    processed_gps_data_observed_object_insert_timestamp = models.DateTimeField()

    def save(self, *args, **kwargs):
        """Populate the geometry from longitude and latitude before saving."""
        lon = self.processed_gps_data_observed_object_longitude
        lat = self.processed_gps_data_observed_object_latitude
        if lon is not None and lat is not None:
            self.processed_gps_data_observed_object_geom = {
                "type": "Point",
                "coordinates": [lon, lat],
            }
        super().save(*args, **kwargs)
