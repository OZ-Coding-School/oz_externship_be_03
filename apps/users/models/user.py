from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from apps.core.models import UUIDBaseModel
from apps.users.enums import Gender
from apps.users.managers.managers import UserManager
from apps.users.validators import validate_korean_phone


class User(AbstractBaseUser, UUIDBaseModel):
    """
    User 모델
    - 로그인 키: email
    """

    USERNAME_FIELD = "email"

    # 회원가입 필수 항목
    REQUIRED_FIELDS = ["nickname", "name", "phone_number", "birthday", "gender"]

    email = models.EmailField(unique=True, null=False)

    name = models.CharField(max_length=30, null=False)

    nickname = models.CharField(max_length=10, unique=True, null=False)

    phone_number = models.CharField(max_length=20, unique=True, validators=[validate_korean_phone], null=False)

    gender = models.CharField(max_length=6, choices=Gender, null=False)

    birthday = models.DateField(null=False)

    profile_img_url = models.URLField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=False, null=False)

    is_staff = models.BooleanField(default=False, null=False)

    is_superuser = models.BooleanField(default=False, null=False)

    # created_at, updated_at 상속

    objects: UserManager = UserManager()

    class Meta:
        db_table = "users"
        # PK 자동 고유 인덱스 생성

    def __str__(self) -> str:
        return f"{self.email} ({self.nickname})"
