"""Consume DEALIoT Kafka `raw.gps` events into the GPS layer."""

from dealdata_common.kafka import DealIotKafkaCommand

from gps_data.ingestion import ingest_dealiot_gps_event


class Command(DealIotKafkaCommand):
    """Consume Kafka messages and persist them through the GPS ingestion path."""

    help = "Consume DEALIoT Kafka raw.gps events into gps_data.WildFiGPSFix."

    bootstrap_servers_env = "DEALDATA_GPS_KAFKA_BOOTSTRAP_SERVERS"
    topic_env = "DEALDATA_GPS_KAFKA_TOPIC"
    group_id_env = "DEALDATA_GPS_KAFKA_GROUP_ID"
    auto_offset_reset_env = "DEALDATA_GPS_KAFKA_AUTO_OFFSET_RESET"
    default_topic = "raw.gps"
    default_group_id = "dealdata-gps-ingest"
    event_label = "GPS"
    ingest_event = staticmethod(ingest_dealiot_gps_event)
