from typing import Any, Dict

from rest_framework import serializers


class SocialAuthRequestSerializer(serializers.Serializer[Dict[str, Any]]):
    provider = serializers.CharField(required=False)
    code = serializers.CharField(help_text="소셜 인가 코드")
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="네이버 로그인 시 필요한 state (카카오는 비워도 됨)",
    )


class SocialAuthResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    detail = serializers.CharField(help_text="응답 메시지", required=True)
    access = serializers.CharField(help_text="JWT access 토큰", required=True)

    @classmethod
    def from_service_result(cls, result: Dict[str, Any]) -> "SocialAuthResponseSerializer":
        return cls(
            {
                "detail": result.get("detail", ""),
                "access": result.get("data", {}).get("access", ""),
                "refresh": result.get("data", {}).get("refresh", ""),
            }
        )
