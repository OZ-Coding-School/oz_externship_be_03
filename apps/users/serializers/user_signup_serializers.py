from __future__ import annotations

from datetime import date
from typing import Any, Dict, Mapping, TypedDict

from rest_framework import serializers

from apps.users.enums import Gender, Role
from apps.users.models import User


class SignupPayload(TypedDict):
    """회원가입 입력 페이로드"""

    email: str
    password: str
    nickname: str
    name: str
    phone_number: str
    birthday: date  # "YYYY-MM-DD"
    gender: Gender
    role: Role


class SignupResponseSerializer(serializers.Serializer[Mapping[str, Any] | Any]):
    """
    응답 detail, data 페이로드
    """

    detail = serializers.CharField(read_only=True)


class UserSignupSerializer(serializers.ModelSerializer[User]):
    """
    회원가입 입력 수집 시리얼라이저
    """

    role = serializers.ChoiceField(
        choices=Role.choices,
        required=False,
        default=Role.USER,
        write_only=True,
        help_text="user|staff|superuser (기본값: user)",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "nickname",
            "name",
            "phone_number",
            "birthday",
            "gender",
            "role",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"validators": []},
            "phone_number": {"validators": []},
        }
