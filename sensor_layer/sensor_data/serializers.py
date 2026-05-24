"""Serializers for sensor ingestion contracts."""

from rest_framework import serializers


class WildFiSensorIngestSerializer(serializers.Serializer):
    """Validate the decoded DEALIoT `raw.sensor` ingestion payload."""

    event_id = serializers.CharField(required=False, allow_blank=True)
    id = serializers.CharField(required=False, allow_blank=True)
    device_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    ingested_at = serializers.DateTimeField(required=False, allow_null=True)
    topic = serializers.CharField(required=False, allow_blank=True)
    source = serializers.CharField(required=False, allow_blank=True)
    mqtt_topic = serializers.CharField(required=False, allow_blank=True)
    key = serializers.CharField(required=False, allow_blank=True)
    qos = serializers.IntegerField(required=False)
    retain = serializers.BooleanField(required=False)
    partition = serializers.IntegerField(required=False)
    offset = serializers.IntegerField(required=False)
    observed_object_id = serializers.UUIDField(required=False, allow_null=True)
    sensor_type = serializers.CharField(required=False, allow_blank=True)
    payload = serializers.JSONField()

    def validate_payload(self, value):
        """The decoded WildFi payload must stay queryable as an object."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        return value


class WildFiSensorBatchSerializer(serializers.Serializer):
    """Validate a batch of decoded DEALIoT `raw.sensor` events."""

    events = WildFiSensorIngestSerializer(many=True)
