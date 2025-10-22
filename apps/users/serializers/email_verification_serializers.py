from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.users.enums import EmailVerificationPurpose, PhoneVerificationPurpose


class EmailVerificationRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """
    이메일 인증 코드 발송(요청) 시 입력 스키마
    - 실제 중복검사/레이트리밋/토큰 생성/발송은 서비스 레이어에서 처리
    """

    email = serializers.EmailField(required=True)
    purpose = serializers.ChoiceField(choices=EmailVerificationPurpose.choices, required=False)


class EmailVerifyCodeSerializer(serializers.Serializer[dict[str, Any]]):
    """
    이메일 인증 코드 검증 시 입력 스키마
    - 실제 코드 일치 여부/만료 여부/목적(purpose) 검증은 서비스 레이어에서 처리
    """

    email = serializers.EmailField(required=True)
    verification_code = serializers.CharField(required=True, max_length=6)
    purpose = serializers.ChoiceField(choices=PhoneVerificationPurpose.choices, required=False)
