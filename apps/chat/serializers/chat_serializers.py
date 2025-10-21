from typing import Any

from rest_framework import serializers


class ChatMessageCreateRequestSerializer(serializers.Serializer[Any]):
    content = serializers.CharField(required=True)


class ChatMessageResponseSerializer(serializers.Serializer[Any]):
    message_id = serializers.IntegerField()
    sender_id = serializers.IntegerField()
    study_group_id = serializers.IntegerField()
    content = serializers.CharField()
    file_url = serializers.URLField(allow_null=True)
    created_at = serializers.DateTimeField()
