from __future__ import annotations

import os

import redis
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

# Redis 설정
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# REDIS DB는 0~15 사이의 정수로 번호 설정해 사용, 설정하지 않을시 기본값 0
# REDIS_DB = int(os.getenv("REDIS_DB", "0"))
# r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


# ---------------------------------------------------------------------------
# 📞 휴대폰 인증 퍼미션
# ---------------------------------------------------------------------------
class PhoneVerifiedPermission(BasePermission):
    """
    특정 purpose(목적)에 대해 '휴대폰 인증'이 완료된 사용자만 접근 가능.
    ex) permission_classes = [IsAuthenticated, PhoneVerifiedPermission]
        purpose = "change_phone"
    """

    message = "휴대폰 인증이 완료되지 않았습니다."
    purpose: str | None = None

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        purpose = getattr(view, "purpose", self.purpose)

        if not user or not user.is_authenticated or not purpose:
            return False

        key = f"verify:phone:{user.id}:{purpose}"
        if not redis_client.exists(key):
            return False

        # 원타임 소모
        redis_client.delete(key)
        return True


# ---------------------------------------------------------------------------
# 📧 이메일 인증 퍼미션
# ---------------------------------------------------------------------------
class EmailVerifiedPermission(BasePermission):
    """
    특정 purpose(목적)에 대해 '이메일 인증'이 완료된 사용자만 접근 가능.
    ex) permission_classes = [IsAuthenticated, EmailVerifiedPermission]
        purpose = "reset_password"
    """

    message = "이메일 인증이 완료되지 않았습니다."
    purpose: str | None = None

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        purpose = getattr(view, "purpose", self.purpose)

        if not user or not user.is_authenticated or not purpose:
            return False

        key = f"verify:email:{user.id}:{purpose}"
        if not redis_client.exists(key):
            return False

        redis_client.delete(key)
        return True
