from typing import Any, Dict

from rest_framework import serializers


class KakaoAuthRequestSerializer(serializers.Serializer[dict[str, Any]]):
    code = serializers.CharField(help_text="카카오 OAuth 인가 코드")


class NaverAuthRequestSerializer(serializers.Serializer[dict[str, Any]]):
    code = serializers.CharField(help_text="네이버 OAuth 인가 코드")
    state = serializers.CharField(help_text="네이버 OAuth state 값")


class SocialAuthResponseSerializer(serializers.Serializer[Dict[str, Any]]):

    detail = serializers.CharField(
        help_text="응답 메시지 (예: 카카오 로그인에 성공했습니다.)",
        required=True,
    )
    access = serializers.CharField(
        help_text="JWT access 토큰 (예: eyJ0eXAiOiJKV1QiLCJh...)",
        required=True,
    )

    @classmethod
    def from_service_result(cls, result: Dict[str, Any]) -> "SocialAuthResponseSerializer":

        return cls(
            {
                "detail": result.get("detail", ""),
                "access": result.get("data", {}).get("access", ""),
            }
        )
