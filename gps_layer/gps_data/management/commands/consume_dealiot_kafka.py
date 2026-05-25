"""Consume DEALIoT Kafka `raw.gps` events into the GPS layer."""

from dealdata_common.kafka import build_dealiot_kafka_command

from gps_data.ingestion import ingest_dealiot_gps_event

Command = build_dealiot_kafka_command(
    service_key="gps",
    event_label="GPS",
    model_path="gps_data.WildFiGPSFix",
    ingest_event=ingest_dealiot_gps_event,
)
