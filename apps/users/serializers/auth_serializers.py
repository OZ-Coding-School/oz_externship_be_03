from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers


# ---- 입력 스키마 ----
class LoginRequestSerializer(serializers.Serializer[Dict[str, Any]]):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )


class TokenRefreshRequestSerializer(serializers.Serializer[Dict[str, Any]]):
    refresh = serializers.CharField(required=True, allow_blank=False)


# ---- 출력 스키마 ----
class LoginResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    access = serializers.CharField()


class TokenRefreshResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    access = serializers.CharField()
