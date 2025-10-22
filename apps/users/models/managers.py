from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.contrib.auth.base_user import BaseUserManager
from django.db import models

if TYPE_CHECKING:
    from .social_user import SocialUser
    from .user import User


class UserManager(BaseUserManager["User"]):
    def get_active_user(self) -> models.QuerySet["User"]:
        """
        활성화 유저 확인
        """
        qs: models.QuerySet["User"] = self.get_queryset()
        return qs.filter(is_active=True)

    def exists_email(self, email: str) -> bool:
        """
        이메일 중복 확인
        """
        return self.get_active_user().filter(email=email).exists()

    def exists_nickname(self, nickname: str) -> bool:
        """
        닉네임 중복 확인
        """
        return self.get_active_user().filter(nickname=nickname).exists()

    def create_user(self, email: str, password: Optional[str] = None, **extra_fields: object) -> "User":
        """유저 생성: 이메일 정규화 적용 + 비밀번호 설정(None이면 unusable)"""
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


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
