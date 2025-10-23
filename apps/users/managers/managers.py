from typing import TYPE_CHECKING, Optional

from django.contrib.auth.base_user import BaseUserManager
from django.db import models

if TYPE_CHECKING:  # pragma: no cover
    from apps.users.models.social_user import SocialUser
    from apps.users.models.user import User


# ---------------------------------------------------------------------
# UserManager
# ---------------------------------------------------------------------
class UserManager(BaseUserManager["User"]):
    def get_active_user(self) -> models.QuerySet["User"]:
        return self.filter(is_active=True)

    def create_user(self, email: str, password: Optional[str] = None, **extra_fields: object) -> "User":
        """유저 생성: 이메일 정규화 적용 + 비밀번호 설정(None이면 unusable)"""
        user = self.model(email=self.normalize_email(email), **extra_fields)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields: object) -> "User":
        """어드민 생성"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not (extra_fields.get("is_staff") and extra_fields.get("is_superuser")):
            raise ValueError("관리자 계정을 생성할 수 없습니다.")

        return self.create_user(email, password, **extra_fields)


# ---------------------------------------------------------------------
# SocialUserManager
# ---------------------------------------------------------------------
class SocialUserManager(models.Manager["SocialUser"]):
    def kakao_users(self) -> models.QuerySet["SocialUser"]:
        return self.filter(provider="kakao")

    def naver_users(self) -> models.QuerySet["SocialUser"]:
        return self.filter(provider="naver")
