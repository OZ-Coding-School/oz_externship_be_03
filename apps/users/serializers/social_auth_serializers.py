from typing import Any, Dict

from rest_framework import serializers


class KakaoAuthRequestSerializer(serializers.Serializer[Dict[str, Any]]):
    code = serializers.CharField(
        help_text="카카오 로그인 인가 코드 (Mock 모드에서는 FAKE_KAKAO_CODE 입력)",
    )


class NaverSocialRequestSerializer(serializers.Serializer[Dict[str, Any]]):
    code = serializers.CharField(
        help_text="네이버 로그인 인가 코드 (Mock 모드에서는 FAKE_NAVER_CODE 입력)",
    )
    state = serializers.CharField(help_text="네이버 로그인 시 필요한 state 값 (Mock 모드에서는 FAKE_STATE 입력)")


class SocialAuthResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    detail = serializers.CharField(help_text="응답 메시지", required=True)
    access = serializers.CharField(help_text="JWT access 토큰", required=True)

    @classmethod
    def from_service_result(cls, result: Dict[str, Any]) -> "SocialAuthResponseSerializer":
        return cls(
            {
                "detail": result.get("detail", ""),
                "access": result.get("data", {}).get("access", ""),
            }
        )
