from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers

from apps.users.enums import PhoneVerificationPurpose
from apps.users.validators import validate_korean_phone

PURPOSE_CHOICES: tuple[tuple[str, str], ...] = (
    (PhoneVerificationPurpose.SIGNUP, "회원가입"),
    (PhoneVerificationPurpose.FIND_EMAIL, "아이디 찾기"),
)


# -------------------------------
# 공개용 (signup / find_email)
# -------------------------------


class SendCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 요청 - 회원가입, 이메일 찾기
    """

    phone_number = serializers.CharField(
        write_only=True,
        validators=[validate_korean_phone],
        help_text="국내 휴대폰 번호 (예: 01012345677, 공백이나 하이픈 없이 숫자만)",
    )
    purpose = serializers.ChoiceField(
        choices=PURPOSE_CHOICES,
        write_only=True,
        help_text="요청 목적 (signup | find_email)",
    )

    class Meta:
        ref_name = "PhoneVerificationSendCodeSerializer"


class ConfirmCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 요청 - 회원가입, 이메일 찾기
    """

    phone_number = serializers.CharField(
        write_only=True,
        validators=[validate_korean_phone],
        help_text="국내 휴대폰 번호",
    )
    purpose = serializers.ChoiceField(
        choices=PURPOSE_CHOICES,
        write_only=True,
        help_text="요청 목적 (signup | find_email)",
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


# -------------------------------
# 인증용 (change_phone) — 서버가 purpose 고정
# -------------------------------


class ChangePhoneSendCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 요청 - 휴대폰 번호 변경 전용
    """

    phone_number = serializers.CharField(
        write_only=True,
        validators=[validate_korean_phone],
        help_text="국내 휴대폰 번호 (예: 01012345677, 공백이나 하이픈 없이 숫자만)",
    )

    def validate(self, attrs: Dict[str, Any]) -> Any:
        attrs["purpose"] = PhoneVerificationPurpose.CHANGE_PHONE
        return attrs

    class Meta:
        ref_name = "PhoneVerificationChangePhoneSendCodeSerializer"


class ChangePhoneConfirmCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 요청 - 휴대폰 번호 변경 전용
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

    def validate(self, attrs: Dict[str, Any]) -> Any:
        attrs["purpose"] = PhoneVerificationPurpose.CHANGE_PHONE
        return attrs

    class Meta:
        ref_name = "PhoneVerificationChangePhoneConfirmCodeSerializer"


# -------------------------------
# 공통 — 응답용 시리얼라이저
# -------------------------------


class SendCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 응답 - 메타데이터
    """

    request_id = serializers.CharField(help_text="서버가 발급한 인증요청 식별자")
    expires_in = serializers.IntegerField(help_text="인증코드 유효 시간(초)")
    cooldown = serializers.IntegerField(help_text="재전송 가능 대기 시간(초)")
    max_attempts = serializers.IntegerField(help_text="허용되는 최대 검증 시도 횟수")

    class Meta:
        ref_name = "PhoneVerificationSendCodeResponseSerializer"


class ConfirmCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 응답 - 메타데이터
    """

    verify_token = serializers.CharField(help_text="다음 단계에서 1회용으로 소비할 검증 토큰")
    expires_in = serializers.IntegerField(help_text="토큰 만료까지 남은 시간(초)")

    class Meta:
        ref_name = "PhoneVerificationConfirmCodeResponseSerializer"
