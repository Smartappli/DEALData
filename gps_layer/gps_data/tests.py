"""Tests for the gps_data application."""

from gps_data.models import GPSSensor


def test_gps_sensor_string_representation() -> None:
    """GPS sensors are represented by their code."""
    gps_sensor = GPSSensor(gps_sensors_code="GPS-001")

    assert str(gps_sensor) == "GPS-001"
