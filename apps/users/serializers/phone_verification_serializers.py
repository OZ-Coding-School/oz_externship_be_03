from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers

from apps.users.validators import validate_korean_phone

# -------------------------------
# 휴대폰 인증코드 전송 시리얼라이저
# -------------------------------


class SendCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 요청
    """

    phone_number = serializers.CharField(
        write_only=True,
        validators=[validate_korean_phone],
        help_text="국내 휴대폰 번호 (예: 01012345677, 공백이나 하이픈 없이 숫자만)",
    )

    class Meta:
        ref_name = "PhoneVerificationSendCodeSerializer"


class SendCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 응답
    """

    request_id = serializers.CharField(help_text="서버가 발급한 인증요청 식별자")
    expires_in = serializers.IntegerField(help_text="인증코드 유효 시간(초)")
    cooldown = serializers.IntegerField(help_text="재전송 가능 대기 시간(초)")
    max_attempts = serializers.IntegerField(help_text="허용되는 최대 검증 시도 횟수")

    class Meta:
        ref_name = "PhoneVerificationSendCodeResponseSerializer"


# -------------------------------
# 휴대폰 인증코드 확인 시리얼라이저
# -------------------------------


class ConfirmCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 요청
    """

    phone_number = serializers.CharField(
        write_only=True,
        validators=[validate_korean_phone],
        help_text="국내 휴대폰 번호",
    )
    request_id = serializers.CharField(
        write_only=True,
        help_text="인증코드 전송 시 발급된 request_id (Twilio verification.sid)",
    )
    code = serializers.RegexField(
        r"^\d{6}$",
        write_only=True,
        help_text="인증코드 6자리 숫자",
    )

    class Meta:
        ref_name = "PhoneVerificationConfirmCodeSerializer"


class ConfirmCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 응답
    """

    phone_verify_token = serializers.CharField(help_text="다음 단계에서 1회용으로 소비할 검증 토큰")
    expires_in = serializers.IntegerField(help_text="토큰 만료까지 남은 시간(초)")

    class Meta:
        ref_name = "PhoneVerificationConfirmCodeResponseSerializer"
