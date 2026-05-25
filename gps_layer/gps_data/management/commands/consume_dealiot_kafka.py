"""Consume DEALIoT Kafka `raw.gps` events into the GPS layer."""

from __future__ import annotations

import json
import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from rest_framework import status

from gps_data.ingestion import ingest_dealiot_gps_event


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


class Command(BaseCommand):
    """Consume Kafka messages and persist them through the GPS ingestion path."""

    help = "Consume DEALIoT Kafka raw.gps events into gps_data.WildFiGPSFix."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--bootstrap-servers",
            default=_env(
                "DEALDATA_GPS_KAFKA_BOOTSTRAP_SERVERS",
                "DEALDATA_KAFKA_BOOTSTRAP_SERVERS",
                "KAFKA_BOOTSTRAP_SERVERS",
                default="kafka1:9092,kafka2:9092,kafka3:9092",
            ),
        )
        parser.add_argument(
            "--topic",
            default=_env("DEALDATA_GPS_KAFKA_TOPIC", default="raw.gps"),
        )
        parser.add_argument(
            "--group-id",
            default=_env(
                "DEALDATA_GPS_KAFKA_GROUP_ID",
                default="dealdata-gps-ingest",
            ),
        )
        parser.add_argument(
            "--auto-offset-reset",
            choices=["earliest", "latest", "none"],
            default=_env(
                "DEALDATA_GPS_KAFKA_AUTO_OFFSET_RESET",
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
        try:
            from kafka import KafkaConsumer
        except ImportError as exc:
            raise CommandError(
                "kafka-python is required to consume DEALIoT Kafka topics.",
            ) from exc

        bootstrap_servers = _csv(options["bootstrap_servers"])
        if not bootstrap_servers:
            raise CommandError("At least one Kafka bootstrap server is required.")

        consumer = KafkaConsumer(
            options["topic"],
            bootstrap_servers=bootstrap_servers,
            group_id=options["group_id"],
            enable_auto_commit=False,
            auto_offset_reset=options["auto_offset_reset"],
        )
        self.stdout.write(
            "Consuming DEALIoT GPS events "
            f"topic={options['topic']} group_id={options['group_id']}",
        )

        try:
            while True:
                records = consumer.poll(
                    timeout_ms=options["poll_timeout_ms"],
                    max_records=options["max_records"],
                )
                if not records:
                    if options["once"]:
                        break
                    continue

                inserted = 0
                duplicates = 0
                rejected = 0
                for messages in records.values():
                    for message in messages:
                        payload = _decode_json(message.value)
                        if payload is None:
                            rejected += 1
                            self.stderr.write(
                                "Rejected non-object or invalid JSON Kafka message "
                                f"topic={message.topic} partition={message.partition} "
                                f"offset={message.offset}",
                            )
                            continue

                        close_old_connections()
                        body, response_status = ingest_dealiot_gps_event(payload)
                        if response_status == status.HTTP_201_CREATED:
                            inserted += 1
                        elif response_status == status.HTTP_200_OK and body.get(
                            "duplicate",
                        ):
                            duplicates += 1
                        elif response_status == status.HTTP_400_BAD_REQUEST:
                            rejected += 1
                            self.stderr.write(
                                "Rejected DEALIoT GPS event "
                                f"offset={message.offset} detail={body.get('detail')}",
                            )
                        else:
                            raise CommandError(
                                "Unexpected GPS ingestion response "
                                f"status={response_status} body={body}",
                            )

                consumer.commit()
                self.stdout.write(
                    "Processed DEALIoT GPS Kafka batch "
                    f"inserted={inserted} duplicates={duplicates} "
                    f"rejected={rejected}",
                )
                if options["once"]:
                    break
        finally:
            consumer.close()
