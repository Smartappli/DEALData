"""Serializers for GPS ingestion contracts."""

from rest_framework import serializers


class WildFiGPSIngestSerializer(serializers.Serializer):
    """Validate the decoded DEALIoT `raw.gps` ingestion payload."""

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
    latitude = serializers.FloatField(required=False)
    lat = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    lon = serializers.FloatField(required=False)
    lng = serializers.FloatField(required=False)
    altitude = serializers.FloatField(required=False, allow_null=True)
    alt = serializers.FloatField(required=False, allow_null=True)
    speed = serializers.FloatField(required=False, allow_null=True)
    heading = serializers.FloatField(required=False, allow_null=True)
    course = serializers.FloatField(required=False, allow_null=True)
    payload = serializers.JSONField(required=False)

    def validate_payload(self, value):
        """The decoded WildFi payload must stay queryable as an object."""
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        return value

    def validate(self, attrs):
        """Require GPS coordinates either at top level or in payload."""
        payload = attrs.get("payload") or {}
        has_latitude = any(
            key in attrs or key in payload for key in ("latitude", "lat")
        )
        has_longitude = any(
            key in attrs or key in payload
            for key in ("longitude", "lon", "lng")
        )
        if not has_latitude:
            raise serializers.ValidationError(
                {"latitude": "This field is required."},
            )
        if not has_longitude:
            raise serializers.ValidationError(
                {"longitude": "This field is required."},
            )
        return attrs


class WildFiGPSBatchSerializer(serializers.Serializer):
    """Validate a batch of decoded DEALIoT `raw.gps` events."""

    events = WildFiGPSIngestSerializer(many=True)
