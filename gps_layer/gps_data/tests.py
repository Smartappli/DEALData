"""Tests for the gps_data application."""

from gps_data.models import GPSSensor, WildFiGPSFix


def test_gps_sensor_string_representation() -> None:
    """GPS sensors are represented by their code."""
    gps_sensor = GPSSensor(gps_sensors_code="GPS-001")

    assert str(gps_sensor) == "GPS-001"


def test_wildfi_gps_fix_from_dealiot_event() -> None:
    """WildFi GPS events keep the DEALIoT envelope and decoded coordinates."""
    event = {
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "ingested_at": "2026-05-24T12:30:03Z",
        "source": "wildfi-mqtt",
        "mqtt_topic": "wildfi/wildfi-17/gps",
        "latitude": 50.6333,
        "longitude": 5.5667,
        "altitude": 121.5,
        "payload": {"fix": 3, "hdop": 0.9},
        "qos": 1,
        "retain": False,
    }

    gps_fix = WildFiGPSFix.from_dealiot_event(event)

    assert gps_fix.wildfi_device_id == "wildfi-17"
    assert gps_fix.dealiot_topic == "raw.gps"
    assert gps_fix.latitude == 50.6333
    assert gps_fix.longitude == 5.5667
    assert gps_fix.payload == {"fix": 3, "hdop": 0.9}
    assert gps_fix.message_metadata == {"qos": 1, "retain": False}
    assert gps_fix.as_geojson() == {
        "type": "Point",
        "coordinates": [5.5667, 50.6333],
    }
