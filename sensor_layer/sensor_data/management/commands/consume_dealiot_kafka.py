"""Consume DEALIoT Kafka `raw.sensor` events into the sensor layer."""

from dealdata_common.kafka import DealIotKafkaCommand

from sensor_data.ingestion import ingest_dealiot_sensor_event


class Command(DealIotKafkaCommand):
    """Consume Kafka messages and persist them through the sensor ingestion path."""

    help = (
        "Consume DEALIoT Kafka raw.sensor events into "
        "sensor_data.WildFiDecodedSensorEvent."
    )

    bootstrap_servers_env = "DEALDATA_SENSOR_KAFKA_BOOTSTRAP_SERVERS"
    topic_env = "DEALDATA_SENSOR_KAFKA_TOPIC"
    group_id_env = "DEALDATA_SENSOR_KAFKA_GROUP_ID"
    auto_offset_reset_env = "DEALDATA_SENSOR_KAFKA_AUTO_OFFSET_RESET"
    default_topic = "raw.sensor"
    default_group_id = "dealdata-sensor-ingest"
    event_label = "sensor"
    ingest_event = staticmethod(ingest_dealiot_sensor_event)
