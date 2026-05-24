"""Test module for the sensor data application."""

import pytest
from rest_framework.test import APIClient
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
    assert sensor_event.payload_hash


@pytest.mark.django_db
def test_wildfi_sensor_ingest_is_idempotent() -> None:
    """Posting the same DEALIoT sensor event twice does not duplicate it."""
    client = APIClient()
    event = {
        "event_id": "sensor-event-1",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "payload": {
            "sensor_type": "temperature",
            "value": 18.5,
            "unit": "C",
        },
    }

    first_response = client.post(
        "/api/ingest/wildfi/sensor/",
        event,
        format="json",
    )
    second_response = client.post(
        "/api/ingest/wildfi/sensor/",
        event,
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.data["duplicate"] is True
    assert WildFiDecodedSensorEvent.objects.count() == 1


@pytest.mark.django_db
def test_wildfi_sensor_batch_ingest_accepts_duplicates() -> None:
    """Batch ingestion reports inserts and duplicates without failing."""
    client = APIClient()
    event = {
        "event_id": "sensor-event-2",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "payload": {
            "sensor_type": "temperature",
            "value": 18.5,
            "unit": "C",
        },
    }

    response = client.post(
        "/api/ingest/wildfi/sensor/batch/",
        {"events": [event, event]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["inserted"] == 1
    assert response.data["duplicates"] == 1
    assert response.data["errors"] == 0
    assert WildFiDecodedSensorEvent.objects.count() == 1


def test_wildfi_sensor_ingest_rejects_scalar_payload() -> None:
    """Sensor validation rejects non-object decoded payloads."""
    client = APIClient()
    event = {
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "payload": 18.5,
    }

    response = client.post(
        "/api/ingest/wildfi/sensor/",
        event,
        format="json",
    )

    assert response.status_code == 400
    assert "payload" in str(response.data["detail"])
