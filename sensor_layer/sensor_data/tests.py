"""Test module for the sensor data application."""

from sensor_data.models import Sensor, SensorData


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
