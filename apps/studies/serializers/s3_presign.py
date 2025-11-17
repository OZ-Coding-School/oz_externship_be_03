from __future__ import annotations

from typing import Any

from rest_framework import serializers


class PresignedRequestSerializer(serializers.Serializer[Any]):
    """
    Presigned URL 발급 요청 검증용 Serializer
    """

    file_name = serializers.CharField(required=True, allow_blank=False)
    content_type = serializers.CharField(required=True, allow_blank=False)
    file_size = serializers.IntegerField(required=True, allow_null=False, min_value=1, max_value=10 * 1024 * 1024)
