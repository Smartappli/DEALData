"""Test module for the sensor data application."""

from io import StringIO
import json
import sys
import types
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import Client
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
def test_wildfi_sensor_type_is_inferred_from_dealiot_mqtt_topic() -> None:
    """Sensor ingestion infers a stable type when DEALIoT omits sensor_type."""
    client = APIClient()
    event = {
        "event_id": "sensor-event-imu-topic",
        "device_id": "WF-002",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "source": "wildfi-mqtt",
        "mqtt_topic": "wildfi/tags/WF-002/imu",
        "payload": {
            "accX": -0.05,
            "accY": 0.01,
            "accZ": 0.98,
            "temperatureInDegCel": 18.7,
        },
    }

    response = client.post(
        "/api/ingest/wildfi/sensor/",
        event,
        format="json",
    )

    sensor_event = WildFiDecodedSensorEvent.objects.get(
        event_id="sensor-event-imu-topic",
    )
    assert response.status_code == 201
    assert response.data["sensor_type"] == "imu"
    assert sensor_event.sensor_type == "imu"


@pytest.mark.django_db
def test_wildfi_sensor_type_prefers_explicit_payload_value() -> None:
    """Explicit DEALIoT sensor_type values override topic inference."""
    client = APIClient()
    event = {
        "event_id": "sensor-event-explicit-type",
        "device_id": "WF-003",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "mqtt_topic": "wildfi/tags/WF-003/imu",
        "payload": {"sensor_type": "temperature", "value": 18.5},
    }

    response = client.post(
        "/api/ingest/wildfi/sensor/",
        event,
        format="json",
    )

    assert response.status_code == 201
    assert response.data["sensor_type"] == "temperature"


@pytest.mark.django_db
def test_dealiot_kafka_consumer_persists_sensor_event() -> None:
    """The Kafka worker persists one DEALIoT raw.sensor message."""

    class FakeKafkaConsumer:
        instances = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.polls = 0
            self.committed = False
            self.closed = False
            self.instances.append(self)

        def poll(self, timeout_ms, max_records):
            del timeout_ms, max_records
            if self.polls:
                return {}
            self.polls += 1
            event = {
                "event_id": "sensor-event-kafka",
                "device_id": "WF-004",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "mqtt_topic": "wildfi/tags/WF-004/environment",
                "payload": {"temperatureInDegCel": 18.7},
            }
            message = types.SimpleNamespace(
                value=json.dumps(event).encode("utf-8"),
                topic="raw.sensor",
                partition=0,
                offset=11,
            )
            return {"raw.sensor-0": [message]}

        def commit(self):
            self.committed = True

        def close(self):
            self.closed = True

    fake_kafka = types.SimpleNamespace(KafkaConsumer=FakeKafkaConsumer)

    with patch.dict(sys.modules, {"kafka": fake_kafka}):
        call_command(
            "consume_dealiot_kafka",
            "--once",
            "--bootstrap-servers",
            "unit:9092",
            stdout=StringIO(),
            stderr=StringIO(),
        )

    sensor_event = WildFiDecodedSensorEvent.objects.get(
        event_id="sensor-event-kafka",
    )
    assert sensor_event.sensor_type == "environment"
    assert FakeKafkaConsumer.instances[0].committed is True
    assert FakeKafkaConsumer.instances[0].closed is True


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


@pytest.mark.django_db
def test_wildfi_sensor_ingest_rejects_invalid_token(settings) -> None:
    """Ingestion rejects requests with a wrong shared token."""
    settings.DEALDATA_INGEST_TOKEN = "expected-token"
    client = APIClient()
    event = {
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "payload": {"sensor_type": "temperature", "value": 18.5},
    }

    response = client.post(
        "/api/ingest/wildfi/sensor/",
        event,
        format="json",
        HTTP_X_DEALDATA_INGEST_TOKEN="wrong-token",
    )

    assert response.status_code == 403
    assert WildFiDecodedSensorEvent.objects.count() == 0


@pytest.mark.django_db
def test_wildfi_sensor_batch_ingest_accepts_array_body() -> None:
    """Batch ingestion accepts a bare JSON array from DEALIoT."""
    client = APIClient()
    event = {
        "event_id": "sensor-event-array",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "payload": {"sensor_type": "temperature", "value": 18.5},
    }

    response = client.post(
        "/api/ingest/wildfi/sensor/batch/",
        [event],
        format="json",
    )

    assert response.status_code == 200
    assert response.data["inserted"] == 1


@pytest.mark.django_db
def test_wildfi_sensor_list_filters_by_device_type_and_time() -> None:
    """Sensor list endpoint filters and paginates stored events."""
    client = APIClient()
    first = {
        "event_id": "sensor-list-1",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "payload": {"sensor_type": "temperature", "value": 18.5},
    }
    second = {
        "event_id": "sensor-list-2",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T13:30:00Z",
        "payload": {"sensor_type": "humidity", "value": 62},
    }
    client.post("/api/ingest/wildfi/sensor/", first, format="json")
    client.post("/api/ingest/wildfi/sensor/", second, format="json")

    response = client.get(
        "/api/wildfi/sensor/",
        {
            "device_id": "wildfi-17",
            "sensor_type": "temperature",
            "from": "2026-05-24T12:00:00Z",
            "to": "2026-05-24T13:00:00Z",
            "limit": "10",
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["sensor_type"] == "temperature"
    assert response.data["results"][0]["payload"]["value"] == 18.5


def test_wildfi_sensor_list_rejects_invalid_datetime() -> None:
    """Sensor list endpoint validates date filters."""
    response = APIClient().get("/api/wildfi/sensor/", {"from": "not-a-date"})

    assert response.status_code == 400
    assert "from" in response.data["detail"]


@pytest.mark.django_db
def test_sensor_metrics_exposes_prometheus_counts() -> None:
    """Metrics endpoint exposes stored sensor event counters."""
    client = APIClient()
    event = {
        "event_id": "sensor-metric-1",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "payload": {"sensor_type": "temperature", "value": 18.5},
    }
    client.post("/api/ingest/wildfi/sensor/", event, format="json")

    response = Client().get("/metrics/")

    assert response.status_code == 200
    assert "dealdata_sensor_wildfi_events_total 1" in response.content.decode()


@pytest.mark.django_db
def test_health_ready_reports_database_available() -> None:
    """Readiness checks database access."""
    response = Client().get("/health/ready/")

    assert response.status_code == 200
    assert response.json()["database"] == "available"


@pytest.mark.django_db
def test_sensor_event_direct_save_populates_payload_hash() -> None:
    """Directly-created sensor events still receive an idempotency hash."""
    event = WildFiDecodedSensorEvent.from_dealiot_event(
        {
            "device_id": "wildfi-17",
            "timestamp": "2026-05-24T12:30:00Z",
            "payload": {"sensor_type": "temperature", "value": 18.5},
        },
    )
    event.payload_hash = ""

    event.save()

    assert event.payload_hash
