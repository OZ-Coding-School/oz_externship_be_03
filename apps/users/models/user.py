from __future__ import annotations

import uuid as _uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import BaseModel


class User(AbstractBaseUser, BaseModel):
    """
    User 모델
    - 로그인 키: email
    """

    USERNAME_FIELD = "email"
    last_login = None

    # 회원가입 필수 항목
    REQUIRED_FIELDS = ["nickname", "name", "phone_number", "birthday", "gender"]

    uuid = models.UUIDField(default=_uuid.uuid4, unique=True)

    email = models.EmailField(unique=True)

    name = models.CharField(max_length=30)

    nickname = models.CharField(max_length=10, unique=True)

    phone_validator = RegexValidator(
        regex=r"^010\d{8}$",
        message="예) 01012345678",
    )
    phone_number = models.CharField(max_length=20, unique=True, validators=[phone_validator])

    GENDER = (
        ("M", "남"),
        ("F", "여"),
    )
    gender = models.CharField(max_length=6, choices=GENDER)

    birthday = models.DateField()

    profile_img_url = models.URLField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=False)

    is_staff = models.BooleanField(default=False)

    is_superuser = models.BooleanField(default=False)

    # created_at, updated_at 상속

    class Meta:
        db_table = "users"
        # PK 자동 고유 인덱스 생성

    def __str__(self) -> str:
        return f"{self.email} ({self.nickname})"
