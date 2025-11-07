from typing import Any, Dict

from rest_framework import serializers


class SocialAuthRequestSerializer(serializers.Serializer[Dict[str, Any]]):

    code = serializers.CharField(
        help_text="OAuth 인가 코드 (카카오/네이버 공통)",
        required=True,
    )
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="네이버 로그인용 state 값 (카카오는 불필요)",
    )


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
