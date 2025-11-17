from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING, Any, Optional, Tuple

from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone

from apps.users.models.withdrawal import Withdrawal

if TYPE_CHECKING:
    from ..models.social_user import SocialUser
    from ..models.user import User


class UserQuerySet(models.QuerySet["User"]):
    def active(self) -> "UserQuerySet":
        return self.filter(is_active=True)

    def inactive(self) -> "UserQuerySet":
        return self.filter(is_active=False)

    def users(self) -> "UserQuerySet":
        return self.exclude(is_staff=True, is_superuser=True)

    def staff(self) -> "UserQuerySet":
        return self.filter(is_staff=True, is_superuser=False)

    def superusers(self) -> "UserQuerySet":
        return self.filter(is_superuser=True)

    def exists_email(self, email: str) -> bool:
        return self.filter(email__iexact=email).exists()

    def exists_phone(self, phone_number: str) -> bool:
        return self.filter(phone_number=phone_number).exists()

    def exists_nickname(self, nickname: str) -> bool:
        return self.filter(nickname__iexact=nickname).exists()


class UserManager(BaseUserManager["User"]):
    def get_queryset(self) -> UserQuerySet:
        return UserQuerySet(self.model, using=self._db)

    def active(self) -> UserQuerySet:
        return self.get_queryset().active()

    def inactive(self) -> UserQuerySet:
        return self.get_queryset().inactive()

    def withdrawal_pending(self) -> models.QuerySet["User"]:
        """
        탈퇴 상태:
        - is_active=False
        - Withdrawal 테이블에 해당 user_id 존재
        """
        return self.get_queryset().filter(
            is_active=False,
            id__in=Withdrawal.objects.values_list("user_id", flat=True),
        )

    def users(self) -> UserQuerySet:
        return self.get_queryset().users()

    def exists_email(self, email: str) -> bool:
        """
        이메일 중복 확인
        """
        return self.get_queryset().exists_email(email)

    def exists_phone(self, phone_number: str) -> bool:
        """
        휴대폰 번호 중복 확인
        """
        return self.get_queryset().exists_phone(phone_number)

    def exists_nickname(self, nickname: str) -> bool:
        """
        닉네임 중복 확인
        """
        return self.get_queryset().exists_nickname(nickname)

    def is_email_blocked_by_recent_withdrawal(self, email: str) -> Tuple[bool, Optional[datetime]]:
        """
        최근 탈퇴로 인한 재가입 차단 상태와 차단 만료시각(block_until) 반환
        """
        email = self.normalize_email(email)
        now = timezone.now()

        user = self.get_queryset().inactive().filter(email=email).first()

        if not user:
            return False, None

        due_date = (
            Withdrawal.objects.filter(user_id=user.id).order_by("-due_date").values_list("due_date", flat=True).first()
        )

        if not due_date:
            return False, None

        block_until = timezone.make_aware(datetime.combine(due_date, time(23, 59, 59)))

        if block_until > now:
            return True, block_until
        return False, None

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
