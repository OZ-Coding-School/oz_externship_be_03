from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers


class EmailVerificationRequestSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    이메일 인증코드 전송 요청
    """

    email = serializers.EmailField(
        required=True,
        write_only=True,
        help_text="인증 코드를 받을 이메일 주소",
    )

    class Meta:
        ref_name = "EmailVerificationSendCodeSerializer"


class EmailVerificationSendCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    이메일 인증코드 전송 응답 - 메타데이터
    """

    request_id = serializers.CharField(help_text="서버가 발급한 인증요청 식별자")
    expires_in = serializers.IntegerField(help_text="인증코드 유효 시간(초)")
    cooldown = serializers.IntegerField(help_text="재전송 가능 대기 시간(초)")
    max_attempts = serializers.IntegerField(help_text="허용되는 최대 검증 시도 횟수")

    class Meta:
        ref_name = "EmailVerificationSendCodeResponseSerializer"


class EmailVerifyCodeSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    이메일 인증코드 확인 요청
    """

    email = serializers.EmailField(
        required=True,
        write_only=True,
        help_text="인증 받은 이메일 주소",
    )
    verification_code = serializers.RegexField(
        r"^\d{6}$",
        required=True,
        write_only=True,
        help_text="인증코드 6자리 숫자",
    )

    request_id = serializers.CharField(
        required=True,
        write_only=True,
        help_text="코드 전송 시 발급된 request_id (내부 발송 트래킹용)",
    )

    class Meta:
        ref_name = "EmailVerificationConfirmCodeSerializer"


class EmailVerifyCodeResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    이메일 인증코드 확인 응답
    """

    email_verify_token = serializers.CharField(help_text="다음 단계에서 1회용으로 소비할 검증 토큰")
    expires_in = serializers.IntegerField(help_text="토큰 만료까지 남은 시간(초)")

    class Meta:
        ref_name = "EmailVerificationConfirmCodeResponseSerializer"
