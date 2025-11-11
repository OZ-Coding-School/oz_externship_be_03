from typing import Any

from rest_framework import serializers


class BookmarkToggleSerializer(serializers.Serializer[Any]):
    recruitment_id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    is_bookmarked = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)
