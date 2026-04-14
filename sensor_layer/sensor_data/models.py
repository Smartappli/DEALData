"""Data models for the sensor layer."""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.db.models import F
from uuid_utils import uuid7

from research.core_layer.core_data.models import ObservedObject


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
    sensor_observed_object_object = models.ForeignKey(
        ObservedObject,
        on_delete=models.CASCADE,
        related_name="sensor_observed_object_object",
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
                condition=F("sensor_observed_object_end_time")
                >= F("sensor_observed_object_start_time"),
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
    sensor_data_observed_object_object = models.ForeignKey(
        ObservedObject,
        on_delete=models.CASCADE,
        related_name="sensor_data_observed_object_object",
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
