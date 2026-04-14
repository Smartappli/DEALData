"""Data models for the GPS layer."""

from __future__ import annotations

from typing import ClassVar

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.db.models import F
from uuid_utils import uuid7


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
    observed_object_gps_sensor_observed_object = models.ForeignKey(
        "core_data.ObservedObject",
        on_delete=models.CASCADE,
        related_name="observed_object_link",
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
                condition=F("observed_object_start_time")
                <= F("observed_object_end_time"),
                name="ck_timestamp_start_before_end",
            ),
            models.UniqueConstraint(
                fields=[
                    "observed_object_gps_sensor_observed_object",
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
    processed_gps_data_observed_object = models.ForeignKey(
        "core_data.ObservedObject",
        on_delete=models.CASCADE,
        related_name="observed_object_link2",
    )
    processed_gps_data_observed_object_acquisition_time = models.DateTimeField()
    processed_gps_data_observed_object_longitude = models.FloatField()
    processed_gps_data_observed_object_latitude = models.FloatField()
    processed_gps_data_observed_object_geom = models.PointField(
        srid=4326,
        spatial_index=True,
    )
    processed_gps_data_observed_object_insert_timestamp = models.DateTimeField()

    def save(self, *args, **kwargs):
        """Populate the geometry from longitude and latitude before saving."""
        lon = self.processed_gps_data_observed_object_longitude
        lat = self.processed_gps_data_observed_object_latitude
        if lon is not None and lat is not None:
            self.processed_gps_data_observed_object_geom = Point(
                lon,
                lat,
                srid=4326,
            )
        super().save(*args, **kwargs)
