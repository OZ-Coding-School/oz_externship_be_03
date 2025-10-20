from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.users.models.withdrawal import Withdrawal

User = get_user_model()


class UserWithdrawalsSerializer(serializers.ModelSerializer[Withdrawal]):
    """
    회원 탈퇴 요청 Serializer
    - Withdrawal 모델 기반
    - 입력값 검증만 수행
    - 실제 탈퇴 처리(로그아웃, 토큰 무효화, is_active=False 등)는 service에서 담당
    """

    class Meta:
        model = Withdrawal
        fields = ["reason", "reason_detail"]
        extra_kwargs = {
            "reason": {"required": True},
            "reason_detail": {"required": True, "max_length": 500},
        }


class UserWithdrawalsRecoverySerializer(serializers.Serializer[Dict[str, Any]]):
    """
    탈퇴 계정 복구 Serializer\
    - 토큰 형식 검증만 수행, 비즈니스 로직(토큰 검증/소모, 계정 활성화, withdrawals 삭제)은 서비스에서 처리
    """

    verify_token = serializers.CharField(write_only=True, required=True)

