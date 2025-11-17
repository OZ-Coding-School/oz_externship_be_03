from typing import Any

from rest_framework import serializers


class BookmarkToggleSerializer(serializers.Serializer[Any]):
    recruitment_uuid = serializers.UUIDField(read_only=True)
    is_bookmarked = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)
