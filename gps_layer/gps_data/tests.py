"""Tests for the gps_data application."""

from io import StringIO
import json
from secrets import token_urlsafe
import sys
import types
from unittest import TestCase
from unittest.mock import patch

import pytest
from gps_data.models import GPSSensor, ProcessedGPSDataObservedObject, WildFiGPSFix
from dealdata_common.views import INVALID_LIST_QUERY_PARAMETERS_DETAIL
from django.core.management import call_command
from django.db import DatabaseError
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

CHECK = TestCase()


def test_gps_sensor_string_representation() -> None:
    """GPS sensors are represented by their code."""
    gps_sensor = GPSSensor(gps_sensors_code="GPS-001")

    CHECK.assertEqual(str(gps_sensor), "GPS-001")


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

    CHECK.assertEqual(gps_fix.wildfi_device_id, "wildfi-17")
    CHECK.assertEqual(gps_fix.dealiot_topic, "raw.gps")
    CHECK.assertEqual(gps_fix.latitude, 50.6333)
    CHECK.assertEqual(gps_fix.longitude, 5.5667)
    CHECK.assertEqual(gps_fix.payload, {"fix": 3, "hdop": 0.9})
    CHECK.assertEqual(gps_fix.message_metadata, {"qos": 1, "retain": False})
    CHECK.assertEqual(
        gps_fix.as_geojson(),
        {
            "type": "Point",
            "coordinates": [5.5667, 50.6333],
        },
    )
    CHECK.assertTrue(gps_fix.payload_hash)


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

    CHECK.assertEqual(first_response.status_code, 201)
    CHECK.assertEqual(second_response.status_code, 200)
    CHECK.assertIs(second_response.data["duplicate"], True)
    CHECK.assertEqual(WildFiGPSFix.objects.count(), 1)


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
    CHECK.assertEqual(response.status_code, 201)
    CHECK.assertEqual(gps_fix.altitude, 411.2)
    CHECK.assertEqual(gps_fix.speed, 1.8)
    CHECK.assertEqual(gps_fix.heading, 84.5)


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
    CHECK.assertEqual(gps_fix.altitude, 411.2)
    CHECK.assertIs(FakeKafkaConsumer.instances[0].committed, True)
    CHECK.assertIs(FakeKafkaConsumer.instances[0].closed, True)


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

    CHECK.assertEqual(response.status_code, 200)
    CHECK.assertEqual(response.data["inserted"], 1)
    CHECK.assertEqual(response.data["duplicates"], 1)
    CHECK.assertEqual(response.data["errors"], 0)
    CHECK.assertEqual(WildFiGPSFix.objects.count(), 1)


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

    CHECK.assertEqual(response.status_code, 400)
    CHECK.assertIn("longitude", str(response.data["detail"]))


@pytest.mark.django_db
def test_wildfi_gps_ingest_rejects_invalid_token(settings) -> None:
    """Ingestion rejects requests with a wrong shared token."""
    settings.DEALDATA_INGEST_TOKEN = token_urlsafe(32)
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
        HTTP_X_DEALDATA_INGEST_TOKEN=f"wrong-{settings.DEALDATA_INGEST_TOKEN}",
    )

    CHECK.assertEqual(response.status_code, 403)
    CHECK.assertEqual(WildFiGPSFix.objects.count(), 0)


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

    CHECK.assertEqual(response.status_code, 200)
    CHECK.assertEqual(response.data["inserted"], 1)


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

    CHECK.assertEqual(response.status_code, 200)
    CHECK.assertEqual(response.data["count"], 1)
    CHECK.assertEqual(response.data["results"][0]["device_id"], "wildfi-17")
    CHECK.assertEqual(
        response.data["results"][0]["geojson"],
        {
            "type": "Point",
            "coordinates": [5.5667, 50.6333],
        },
    )


def test_wildfi_gps_list_rejects_invalid_datetime() -> None:
    """GPS list endpoint validates date filters."""
    response = APIClient().get("/api/wildfi/gps/", {"from": "not-a-date"})

    CHECK.assertEqual(response.status_code, 400)
    CHECK.assertEqual(response.data["detail"], INVALID_LIST_QUERY_PARAMETERS_DETAIL)


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

    CHECK.assertEqual(response.status_code, 200)
    CHECK.assertIn("dealdata_gps_wildfi_events_total 1", response.content.decode())


@pytest.mark.django_db
def test_health_ready_reports_database_available() -> None:
    """Readiness checks database access."""
    response = Client().get("/health/ready/")

    CHECK.assertEqual(response.status_code, 200)
    CHECK.assertEqual(response.json()["database"], "available")


def test_health_ready_reports_generic_database_failure() -> None:
    """Readiness failures do not expose database exception details."""
    with patch("gps_data.views.connections") as mocked_connections:
        mocked_connections.__getitem__.side_effect = DatabaseError(
            "database password leaked",
        )
        response = Client().get("/health/ready/")

    body = response.json()
    CHECK.assertEqual(response.status_code, 503)
    CHECK.assertEqual(body["database"], "unavailable")
    CHECK.assertEqual(body["detail"], "Database connection check failed.")
    CHECK.assertNotIn("password", str(body))


@pytest.mark.parametrize(
    "path",
    ["/health/live/", "/health/ready/", "/metrics/"],
)
def test_observability_endpoints_reject_unsafe_methods(path: str) -> None:
    """Read-only observability endpoints reject unsafe HTTP methods."""
    response = Client().post(path)

    CHECK.assertEqual(response.status_code, 405)
    CHECK.assertEqual(response.headers["Allow"], "GET, HEAD")


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

    CHECK.assertEqual(
        processed.processed_gps_data_observed_object_geom,
        {
            "type": "Point",
            "coordinates": [5.5667, 50.6333],
        },
    )
