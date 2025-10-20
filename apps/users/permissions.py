from __future__ import annotations

import os

from django.core.cache import cache
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class PhoneVerifiedPermission(BasePermission):
    """
    휴대폰 인증 퍼미션

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
        if not cache.get(key):
            return False

        cache.delete(key)
        return True


class EmailVerifiedPermission(BasePermission):
    """
    이메일 인증 퍼미션

    특정 purpose(목적)에 대해 '이메일 인증'이 완료된 사용자만 접근 가능.
    ex) permission_classes = [IsAuthenticated, EmailVerifiedPermission]
        purpose = "change_phone"
    """

    message = "이메일 인증이 완료되지 않았습니다."
    purpose: str | None = None

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        purpose = getattr(view, "purpose", self.purpose)

        if not user or not user.is_authenticated or not purpose:
            return False

        key = f"verify:email:{user.id}:{purpose}"
        if not cache.get(key):
            return False

        cache.delete(key)
        return True
