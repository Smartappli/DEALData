"""Consume DEALIoT Kafka `raw.sensor` events into the sensor layer."""

from __future__ import annotations

import json
import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection
from rest_framework import status

from sensor_data.ingestion import ingest_dealiot_sensor_event


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _decode_json(value: bytes) -> dict[str, Any] | None:
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _close_stale_connections() -> None:
    """Close stale DB connections without breaking transactional test wrappers."""
    if not connection.in_atomic_block:
        close_old_connections()


def _load_kafka_consumer():
    try:
        from kafka import KafkaConsumer
    except ImportError as exc:
        raise CommandError(
            "kafka-python is required to consume DEALIoT Kafka topics.",
        ) from exc
    return KafkaConsumer


def _iter_messages(records):
    for messages in records.values():
        yield from messages


class Command(BaseCommand):
    """Consume Kafka messages and persist them through the sensor ingestion path."""

    help = (
        "Consume DEALIoT Kafka raw.sensor events into "
        "sensor_data.WildFiDecodedSensorEvent."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--bootstrap-servers",
            default=_env(
                "DEALDATA_SENSOR_KAFKA_BOOTSTRAP_SERVERS",
                "DEALDATA_KAFKA_BOOTSTRAP_SERVERS",
                "KAFKA_BOOTSTRAP_SERVERS",
                default="kafka1:9092,kafka2:9092,kafka3:9092",
            ),
        )
        parser.add_argument(
            "--topic",
            default=_env("DEALDATA_SENSOR_KAFKA_TOPIC", default="raw.sensor"),
        )
        parser.add_argument(
            "--group-id",
            default=_env(
                "DEALDATA_SENSOR_KAFKA_GROUP_ID",
                default="dealdata-sensor-ingest",
            ),
        )
        parser.add_argument(
            "--auto-offset-reset",
            choices=["earliest", "latest", "none"],
            default=_env(
                "DEALDATA_SENSOR_KAFKA_AUTO_OFFSET_RESET",
                "DEALDATA_KAFKA_AUTO_OFFSET_RESET",
                default="earliest",
            ),
        )
        parser.add_argument(
            "--poll-timeout-ms",
            type=int,
            default=int(
                _env(
                    "DEALDATA_KAFKA_POLL_TIMEOUT_MS",
                    default="1000",
                ),
            ),
        )
        parser.add_argument(
            "--max-records",
            type=int,
            default=int(_env("DEALDATA_KAFKA_MAX_RECORDS", default="100")),
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Poll once, process available records, then exit.",
        )

    def handle(self, *args, **options) -> None:
        del args
        consumer = self._build_consumer(options)
        self.stdout.write(
            "Consuming DEALIoT sensor events "
            f"topic={options['topic']} group_id={options['group_id']}",
        )

        try:
            self._consume_batches(consumer, options)
        finally:
            consumer.close()

    def _build_consumer(self, options):
        bootstrap_servers = _csv(options["bootstrap_servers"])
        if not bootstrap_servers:
            raise CommandError("At least one Kafka bootstrap server is required.")

        kafka_consumer = _load_kafka_consumer()
        return kafka_consumer(
            options["topic"],
            bootstrap_servers=bootstrap_servers,
            group_id=options["group_id"],
            enable_auto_commit=False,
            auto_offset_reset=options["auto_offset_reset"],
        )

    def _consume_batches(self, consumer, options) -> None:
        while True:
            records = consumer.poll(
                timeout_ms=options["poll_timeout_ms"],
                max_records=options["max_records"],
            )
            if not records:
                if options["once"]:
                    return
                continue

            counts = self._process_records(records)
            consumer.commit()
            self.stdout.write(
                "Processed DEALIoT sensor Kafka batch "
                f"inserted={counts['inserted']} "
                f"duplicates={counts['duplicates']} "
                f"rejected={counts['rejected']}",
            )
            if options["once"]:
                return

    def _process_records(self, records) -> dict[str, int]:
        counts = {"inserted": 0, "duplicates": 0, "rejected": 0}
        for message in _iter_messages(records):
            counts[self._process_message(message)] += 1
        return counts

    def _process_message(self, message) -> str:
        payload = _decode_json(message.value)
        if payload is None:
            self._write_rejected_json(message)
            return "rejected"

        _close_stale_connections()
        body, response_status = ingest_dealiot_sensor_event(payload)
        if response_status == status.HTTP_201_CREATED:
            return "inserted"
        if response_status == status.HTTP_200_OK and body.get("duplicate"):
            return "duplicates"
        if response_status == status.HTTP_400_BAD_REQUEST:
            self.stderr.write(
                "Rejected DEALIoT sensor event "
                f"offset={message.offset} detail={body.get('detail')}",
            )
            return "rejected"

        raise CommandError(
            "Unexpected sensor ingestion response "
            f"status={response_status} body={body}",
        )

    def _write_rejected_json(self, message) -> None:
        self.stderr.write(
            "Rejected non-object or invalid JSON Kafka message "
            f"topic={message.topic} partition={message.partition} "
            f"offset={message.offset}",
        )
