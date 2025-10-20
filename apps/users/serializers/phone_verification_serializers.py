from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers
from rest_framework.fields import Field

from apps.users.validators import validate_korean_phone

PURPOSE_CHOICES: tuple[tuple[str, str], ...] = (
    ("signup", "회원가입"),
    ("find_email", "아이디 찾기"),
    ("change_phone", "휴대폰 변경"),
)


class SendCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 요청
    """

    phone_number = serializers.CharField(
        write_only=True,
        validators=[validate_korean_phone],
        help_text="국내 휴대폰 번호 (예: 01012345677, 공백이나 하이픈 없이 숫자만)",
    )
    purpose = serializers.ChoiceField(
        choices=PURPOSE_CHOICES,
        write_only=True,
        help_text="요청 목적 (signup | find_email | change_phone)",
    )

    class Meta:
        ref_name = "PhoneVerificationSendCodeSerializer"


class SendCodeMetaSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 응답 - 메타데이터
    """

    request_id = serializers.CharField(help_text="서버가 발급한 인증요청 식별자")
    expires_in = serializers.IntegerField(help_text="인증코드 유효 시간(초)")
    cooldown = serializers.IntegerField(help_text="재전송 가능 대기 시간(초)")
    max_attempts = serializers.IntegerField(help_text="허용되는 최대 검증 시도 횟수")

    class Meta:
        ref_name = "PhoneVerificationSendCodeMetaSerializer"


class SendCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 응답
    """

    detail = serializers.CharField(help_text="처리 결과 메시지")
    # data = SendCodeMetaSerializer()

    class Meta:
        ref_name = "PhoneVerificationSendCodeResponseSerializer"

    def get_fields(self) -> dict[str, Field[Any, Any, Any, Any]]:
        fields = super().get_fields()
        fields["data"] = SendCodeMetaSerializer()  # Serializer.data 프로퍼티와의 충돌 회피를 위해 동적 추가
        return fields


class ConfirmCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 요청
    """

    phone_number = serializers.CharField(
        write_only=True,
        validators=[validate_korean_phone],
        help_text="국내 휴대폰 번호",
    )
    purpose = serializers.ChoiceField(
        choices=PURPOSE_CHOICES,
        write_only=True,
        help_text="요청 목적 (signup | find_email | change_phone)",
    )
    code = serializers.RegexField(
        r"^\d{6}$",
        write_only=True,
        help_text="인증코드 6자리 숫자",
    )

    class Meta:
        ref_name = "PhoneVerificationConfirmCodeSerializer"


class ConfirmCodeMetaSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 응답 - 메타데이터
    """

    verify_token = serializers.CharField(help_text="다음 단계에서 1회용으로 소비할 검증 토큰")
    expires_in = serializers.IntegerField(help_text="토큰 만료까지 남은 시간(초)")

    class Meta:
        ref_name = "PhoneVerificationConfirmCodeMetaSerializer"


class ConfirmCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인 응답
    """

    detail = serializers.CharField(help_text="처리 결과 메시지")
    # data = ConfirmCodeMetaSerializer()

    class Meta:
        ref_name = "PhoneVerificationConfirmCodeResponseSerializer"

    def get_fields(self) -> dict[str, Field[Any, Any, Any, Any]]:
        fields = super().get_fields()
        fields["data"] = ConfirmCodeMetaSerializer()  # Serializer.data 프로퍼티와의 충돌 회피를 위해 동적 추가
        return fields
