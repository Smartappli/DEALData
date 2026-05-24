"""Test module for the sensor data application."""

from sensor_data.models import Sensor, SensorData, WildFiDecodedSensorEvent


def test_sensor_string_representation() -> None:
    """Sensors are represented by their code."""
    sensor = Sensor(
        sensor_vendor="Bosch",
        sensor_model="BMP680",
        sensor_code="SENSOR-001",
    )

    assert str(sensor) == "SENSOR-001"


def test_sensor_data_string_representation() -> None:
    """Sensor data values are rendered as strings."""
    sensor_data = SensorData(sensor_data_value={"temperature": 18.5})

    assert str(sensor_data) == "{'temperature': 18.5}"


def test_wildfi_sensor_event_from_dealiot_event() -> None:
    """WildFi sensor events keep the DEALIoT envelope and decoded payload."""
    event = {
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "ingested_at": "2026-05-24T12:30:03Z",
        "source": "wildfi-mqtt",
        "mqtt_topic": "wildfi/wildfi-17/sensor",
        "payload": {
            "sensor_type": "temperature",
            "value": 18.5,
            "unit": "C",
        },
        "qos": 1,
        "retain": False,
    }

    sensor_event = WildFiDecodedSensorEvent.from_dealiot_event(event)

    assert sensor_event.wildfi_device_id == "wildfi-17"
    assert sensor_event.dealiot_topic == "raw.sensor"
    assert sensor_event.sensor_type == "temperature"
    assert sensor_event.payload["value"] == 18.5
    assert sensor_event.message_metadata == {"qos": 1, "retain": False}
