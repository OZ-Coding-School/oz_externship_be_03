from __future__ import annotations

from typing import Any

from rest_framework import serializers


class DupNicknameQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """
    닉네임 중복 확인 쿼리 파라미터
    """

    nickname = serializers.CharField(required=True, trim_whitespace=True)
    case_insensitive = serializers.BooleanField(required=False, default=True)


class DupNicknameDataSerializer(serializers.Serializer[dict[str, Any]]):
    """
    응답 data 필드 스키마
    """

    nickname = serializers.CharField()
    available = serializers.BooleanField()


class DupNicknameResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """
    전체 응답 스키마
    """

    detail = serializers.CharField()
    payload = DupNicknameDataSerializer(source="data")
