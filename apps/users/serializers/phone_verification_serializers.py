# apps/users/serializers/phone_verification_serializers.py
from __future__ import annotations

from typing import Any, Dict, Literal

from django.core.validators import RegexValidator
from rest_framework import serializers

PhonePurpose = Literal["signup", "find_email", "change_phone"]
PURPOSE_CHOICES: tuple[tuple[str, str], ...] = (
    ("signup", "회원가입"),
    ("find_email", "아이디 찾기"),
    ("change_phone", "휴대폰 변경"),
)

# 휴대폰 형식 검증 TODO : 공통으로 뺄 경우 그거 사용하기
phone_validator = RegexValidator(
    regex=r"^010\d{8}$",
    message="휴대폰 번호 형식이 올바르지 않습니다. 예) 01012345678",
)


class PhoneVerificationSendCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 전송 요청
    """

    phone_number = serializers.CharField(write_only=True, validators=[phone_validator])
    purpose = serializers.ChoiceField(choices=PURPOSE_CHOICES, write_only=True)


class PhoneVerificationConfirmCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    휴대폰 인증코드 확인
    """

    phone_number = serializers.CharField(write_only=True, validators=[phone_validator])
    purpose = serializers.ChoiceField(choices=PURPOSE_CHOICES, write_only=True)
    code = serializers.CharField(write_only=True, min_length=6, max_length=6)

    def validate_code(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("인증코드는 숫자 6자리여야 합니다.")
        return value
