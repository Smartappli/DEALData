"""Tests for the gps_data application."""

from io import StringIO
import json
import sys
import types
from unittest.mock import patch

import pytest
from gps_data.models import GPSSensor, ProcessedGPSDataObservedObject, WildFiGPSFix
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient


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
    assert gps_fix.payload_hash


@pytest.mark.django_db
def test_wildfi_gps_ingest_is_idempotent() -> None:
    """Posting the same DEALIoT GPS event twice does not duplicate it."""
    client = APIClient()
    event = {
        "event_id": "gps-event-1",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "latitude": 50.6333,
        "longitude": 5.5667,
        "payload": {"fix": 3},
    }

    first_response = client.post(
        "/api/ingest/wildfi/gps/",
        event,
        format="json",
    )
    second_response = client.post(
        "/api/ingest/wildfi/gps/",
        event,
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.data["duplicate"] is True
    assert WildFiGPSFix.objects.count() == 1


@pytest.mark.django_db
def test_wildfi_gps_ingest_accepts_dealiot_metric_aliases() -> None:
    """GPS ingestion normalizes DEALIoT metric field names."""
    client = APIClient()
    event = {
        "event_id": "gps-event-dealiot-aliases",
        "device_id": "WF-001",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "source": "wildfi-mqtt",
        "mqtt_topic": "wildfi/tags/WF-001/gps",
        "latitude": 47.695,
        "longitude": 9.132,
        "altitude_m": 411.2,
        "speed_m_s": 1.8,
        "heading_deg": 84.5,
        "payload": {"fixType": 3},
    }

    response = client.post(
        "/api/ingest/wildfi/gps/",
        event,
        format="json",
    )

    gps_fix = WildFiGPSFix.objects.get(event_id="gps-event-dealiot-aliases")
    assert response.status_code == 201
    assert gps_fix.altitude == 411.2
    assert gps_fix.speed == 1.8
    assert gps_fix.heading == 84.5


@pytest.mark.django_db
def test_dealiot_kafka_consumer_persists_gps_event() -> None:
    """The Kafka worker persists one DEALIoT raw.gps message."""

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
                "event_id": "gps-event-kafka",
                "device_id": "WF-004",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "latitude": 47.695,
                "longitude": 9.132,
                "altitude_m": 411.2,
            }
            message = types.SimpleNamespace(
                value=json.dumps(event).encode("utf-8"),
                topic="raw.gps",
                partition=0,
                offset=10,
            )
            return {"raw.gps-0": [message]}

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

    gps_fix = WildFiGPSFix.objects.get(event_id="gps-event-kafka")
    assert gps_fix.altitude == 411.2
    assert FakeKafkaConsumer.instances[0].committed is True
    assert FakeKafkaConsumer.instances[0].closed is True


@pytest.mark.django_db
def test_wildfi_gps_batch_ingest_accepts_duplicates() -> None:
    """Batch ingestion reports inserts and duplicates without failing."""
    client = APIClient()
    event = {
        "event_id": "gps-event-2",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "latitude": 50.6333,
        "longitude": 5.5667,
        "payload": {"fix": 3},
    }

    response = client.post(
        "/api/ingest/wildfi/gps/batch/",
        {"events": [event, event]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["inserted"] == 1
    assert response.data["duplicates"] == 1
    assert response.data["errors"] == 0
    assert WildFiGPSFix.objects.count() == 1


def test_wildfi_gps_ingest_rejects_missing_longitude() -> None:
    """GPS validation rejects events without a longitude."""
    client = APIClient()
    event = {
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "latitude": 50.6333,
        "payload": {"fix": 3},
    }

    response = client.post(
        "/api/ingest/wildfi/gps/",
        event,
        format="json",
    )

    assert response.status_code == 400
    assert "longitude" in str(response.data["detail"])


@pytest.mark.django_db
def test_wildfi_gps_ingest_rejects_invalid_token(settings) -> None:
    """Ingestion rejects requests with a wrong shared token."""
    settings.DEALDATA_INGEST_TOKEN = "expected-token"
    client = APIClient()
    event = {
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "latitude": 50.6333,
        "longitude": 5.5667,
        "payload": {"fix": 3},
    }

    response = client.post(
        "/api/ingest/wildfi/gps/",
        event,
        format="json",
        HTTP_X_DEALDATA_INGEST_TOKEN="wrong-token",
    )

    assert response.status_code == 403
    assert WildFiGPSFix.objects.count() == 0


@pytest.mark.django_db
def test_wildfi_gps_batch_ingest_accepts_array_body() -> None:
    """Batch ingestion accepts a bare JSON array from DEALIoT."""
    client = APIClient()
    event = {
        "event_id": "gps-event-array",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "latitude": 50.6333,
        "longitude": 5.5667,
        "payload": {"fix": 3},
    }

    response = client.post(
        "/api/ingest/wildfi/gps/batch/",
        [event],
        format="json",
    )

    assert response.status_code == 200
    assert response.data["inserted"] == 1


@pytest.mark.django_db
def test_wildfi_gps_list_filters_by_device_and_time() -> None:
    """GPS list endpoint filters and paginates stored events."""
    client = APIClient()
    first = {
        "event_id": "gps-list-1",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "latitude": 50.6333,
        "longitude": 5.5667,
        "payload": {"fix": 3},
    }
    second = {
        "event_id": "gps-list-2",
        "device_id": "wildfi-18",
        "timestamp": "2026-05-24T13:30:00Z",
        "latitude": 51.0,
        "longitude": 5.0,
        "payload": {"fix": 3},
    }
    client.post("/api/ingest/wildfi/gps/", first, format="json")
    client.post("/api/ingest/wildfi/gps/", second, format="json")

    response = client.get(
        "/api/wildfi/gps/",
        {
            "device_id": "wildfi-17",
            "from": "2026-05-24T12:00:00Z",
            "to": "2026-05-24T13:00:00Z",
            "limit": "10",
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["device_id"] == "wildfi-17"
    assert response.data["results"][0]["geojson"] == {
        "type": "Point",
        "coordinates": [5.5667, 50.6333],
    }


def test_wildfi_gps_list_rejects_invalid_datetime() -> None:
    """GPS list endpoint validates date filters."""
    response = APIClient().get("/api/wildfi/gps/", {"from": "not-a-date"})

    assert response.status_code == 400
    assert "from" in response.data["detail"]


@pytest.mark.django_db
def test_gps_metrics_exposes_prometheus_counts() -> None:
    """Metrics endpoint exposes stored GPS event counters."""
    client = APIClient()
    event = {
        "event_id": "gps-metric-1",
        "device_id": "wildfi-17",
        "timestamp": "2026-05-24T12:30:00Z",
        "latitude": 50.6333,
        "longitude": 5.5667,
        "payload": {"fix": 3},
    }
    client.post("/api/ingest/wildfi/gps/", event, format="json")

    response = Client().get("/metrics/")

    assert response.status_code == 200
    assert "dealdata_gps_wildfi_events_total 1" in response.content.decode()


@pytest.mark.django_db
def test_health_ready_reports_database_available() -> None:
    """Readiness checks database access."""
    response = Client().get("/health/ready/")

    assert response.status_code == 200
    assert response.json()["database"] == "available"


@pytest.mark.parametrize(
    "path",
    ["/health/live/", "/health/ready/", "/metrics/"],
)
def test_observability_endpoints_reject_unsafe_methods(path: str) -> None:
    """Read-only observability endpoints reject unsafe HTTP methods."""
    response = Client().post(path)

    assert response.status_code == 405
    assert response.headers["Allow"] == "GET, HEAD"


@pytest.mark.django_db
def test_processed_gps_data_populates_geojson() -> None:
    """Processed GPS data mirrors lon/lat into GeoJSON."""
    gps_sensor = GPSSensor.objects.create(
        gps_sensors_code="GPS-GEOJSON",
        gps_sensor_purchase_date="2026-05-24",
        gps_sensor_frequency=60,
    )
    processed = ProcessedGPSDataObservedObject.objects.create(
        processed_gps_data_sensors=gps_sensor,
        processed_gps_data_observed_object_uuid="00000000-0000-0000-0000-000000000001",
        processed_gps_data_observed_object_acquisition_time=timezone.now(),
        processed_gps_data_observed_object_longitude=5.5667,
        processed_gps_data_observed_object_latitude=50.6333,
        processed_gps_data_observed_object_insert_timestamp=timezone.now(),
    )

    assert processed.processed_gps_data_observed_object_geom == {
        "type": "Point",
        "coordinates": [5.5667, 50.6333],
    }
