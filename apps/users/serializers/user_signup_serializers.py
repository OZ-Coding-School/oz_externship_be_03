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


class UserPublicSerializer(serializers.Serializer[Dict[str, Any]]):
    """응답 본문에 포함될 공개용 사용자 정보"""

    email = serializers.EmailField()
    nickname = serializers.CharField()
    name = serializers.CharField()
    phone_number = serializers.CharField(allow_null=True, required=False)
    birthday = serializers.DateField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    status = serializers.CharField()
    created_at = serializers.DateTimeField(allow_null=True, required=False)


class SignupDataSerializer(serializers.Serializer[Dict[str, Any]]):
    """응답 data 페이로드"""

    user = UserPublicSerializer(read_only=True)


class SignupResponseSerializer(serializers.Serializer[Mapping[str, Any] | Any]):
    """
    응답 detail, data 페이로드
    """

    detail = serializers.CharField(read_only=True)
    payload = SignupDataSerializer(read_only=True)

    def to_representation(self, instance: Mapping[str, Any] | Any) -> Dict[str, Any]:
        rep = super().to_representation(instance)
        if "payload" in rep:
            rep["data"] = rep.pop("payload")
        return rep


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
