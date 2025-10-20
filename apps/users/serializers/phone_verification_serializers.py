from __future__ import annotations

from typing import Any, Dict, Literal

from rest_framework import serializers

from apps.users.validators import validate_korean_phone

PhonePurpose = Literal["signup", "find_email", "change_phone"]
PURPOSE_CHOICES: tuple[tuple[str, str], ...] = (
    ("signup", "회원가입"),
    ("find_email", "아이디 찾기"),
    ("change_phone", "휴대폰 변경"),
)


class PhoneVerificationSendCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 요청
    """

    phone_number = serializers.CharField(write_only=True, validators=[validate_korean_phone])
    purpose = serializers.ChoiceField(choices=PURPOSE_CHOICES, write_only=True)


class PhoneVerificationConfirmCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인
    """

    phone_number = serializers.CharField(write_only=True, validators=[validate_korean_phone])
    purpose = serializers.ChoiceField(choices=PURPOSE_CHOICES, write_only=True)
    code = serializers.CharField(write_only=True, min_length=6, max_length=6)

    def validate_code(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("인증코드는 숫자 6자리여야 합니다.")
        return value
