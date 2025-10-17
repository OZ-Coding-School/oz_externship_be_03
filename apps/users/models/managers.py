from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.base_user import BaseUserManager
from django.db import models

if TYPE_CHECKING:
    from .social_user import SocialUser
    from .user import User


class UserManager(BaseUserManager["User"]):
    def active(self) -> models.QuerySet["User"]:
        """
        활성화 유저 확인
        """
        return self.get_queryset().filter(is_active=True)

    def exists_email(self, email: str) -> bool:
        """
        이메일 중복 확인
        """
        return self.active().filter(email=email).exists()

    def exists_nickname(self, nickname: str) -> bool:
        """
        닉네임 중복 확인
        """
        return self.active().filter(nickname=nickname).exists()


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
