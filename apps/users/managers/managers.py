from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from django.contrib.auth.base_user import BaseUserManager
from django.db import models

if TYPE_CHECKING:
    from ..models.social_user import SocialUser
    from ..models.user import User


class UserManager(BaseUserManager["User"]):
    def get_active_user(self) -> models.QuerySet["User"]:
        """
        활성화 유저만 반환
        """
        return self.get_queryset().filter(is_active=True)

    def exists_email(self, email: str, check_active: Optional[bool] = False) -> bool:
        """
        이메일 중복 확인
        기본적으로 모든 유저를 대상으로 확인하지만, `check_active=True`이면 활성화된 유저만 확인함
        """
        if check_active:
            return self.get_active_user().filter(email=email).exists()
        return self.get_queryset().filter(email=email).exists()

    def exists_phone(self, phone_number: str, check_active: Optional[bool] = False) -> bool:
        """
        휴대폰 번호 중복 확인
        기본적으로 모든 유저를 대상으로 확인하지만, `check_active=True`이면 활성화된 유저만 확인함
        """
        if check_active:
            return self.get_active_user().filter(phone_number=phone_number).exists()
        return self.get_queryset().filter(phone_number=phone_number).exists()

    def exists_nickname(self, nickname: str, check_active: Optional[bool] = False) -> bool:
        """
        닉네임 중복 확인
        기본적으로 모든 유저를 대상으로 확인하지만, `check_active=True`이면 활성화된 유저만 확인함
        """
        if check_active:
            return self.get_active_user().filter(nickname=nickname).exists()
        return self.get_queryset().filter(nickname=nickname).exists()

    def create_user(self, email: str, password: Optional[str] = None, **extra_fields: object) -> "User":
        """유저 생성: 이메일 정규화 적용 + 비밀번호 설정(None이면 unusable)"""
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: Optional[str] = None, **extra_fields: Any) -> "User":
        """관리자 유저 생성"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(email, password, **extra_fields)


class SocialUserManager(models.Manager["SocialUser"]):
    def kakao_users(self) -> models.QuerySet["SocialUser"]:
        """
        카카오 연동 계정만
        """
        return self.filter(provider="kakao")

    def naver_users(self) -> models.QuerySet["SocialUser"]:
        """
        네이버 연동 계정만
        """
        return self.filter(provider="naver")
