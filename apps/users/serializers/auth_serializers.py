from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers


# ---- 입력 스키마 ----
class LoginSerializer(serializers.Serializer[Dict[str, Any]]):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )


class TokenRefreshInSerializer(serializers.Serializer[Dict[str, Any]]):
    refresh = serializers.CharField(required=True, allow_blank=False)


# ---- 출력 스키마 ----
class UserBriefSerializer(serializers.Serializer[Dict[str, Any]]):
    email = serializers.EmailField(required=True, allow_blank=False)
    nickname = serializers.CharField(
        max_length=10,
        required=True,
        allow_blank=False,
        allow_null=False,
    )


class TokenObtainOutSerializer(serializers.Serializer[Dict[str, Any]]):
    user = UserBriefSerializer()
    access = serializers.CharField()


class TokenRefreshOutSerializer(serializers.Serializer[Dict[str, Any]]):
    access = serializers.CharField()
