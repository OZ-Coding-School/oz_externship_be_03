from __future__ import annotations

from datetime import date
from typing import Any, Mapping, TypedDict

from rest_framework import serializers

from apps.users.enums import Gender, Role
from apps.users.models import User


class SignupPayload(TypedDict):
    """
    회원가입 입력 페이로드
    """

    email: str
    password: str
    nickname: str
    name: str
    phone_number: str
    birthday: date  # "YYYY-MM-DD"
    gender: Gender
    role: str | None  # TODO: FE에서 넘어오는 값 확인, 임시 "user", "staff", "superuser"


class UserPublicSerializer(serializers.Serializer[dict[str, Any]]):
    """
    응답 본문에 포함될 공개용 사용자 정보
    """

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    nickname = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(read_only=True)
    birthday = serializers.DateField(read_only=True)
    gender = serializers.ChoiceField(choices=Gender.choices, read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class SignupDataSerializer(serializers.Serializer[dict[str, Any]]):
    """
    응답 data 페이로드
    """

    user = UserPublicSerializer(read_only=True)


class SignupResponseSerializer(serializers.Serializer[Mapping[str, Any] | Any]):
    """
    응답 detail, data
    """

    # {"detail": "...", "data": {"user": {...}}}
    detail = serializers.CharField(read_only=True)
    payload = SignupDataSerializer(read_only=True)

    def to_representation(self, instance: Mapping[str, Any] | Any) -> dict[str, Any]:
        rep = super().to_representation(instance)
        if "payload" in rep:
            rep["data"] = rep.pop("payload")
        return rep


class UserSignupSerializer(serializers.ModelSerializer[User]):
    """
    회원가입 입력 수집 시리얼라이저
    - 모든 유효성 검증(중복/코드검증/도메인 규칙)은 서비스단에서 수행.
    - 모델에는 없는 role( user | staff | superuser )을 입력 전용으로 추가.
    - 실제 반영은 서비스에서 role → is_staff/is_superuser 매핑 처리.
    """

    role = serializers.ChoiceField(
        choices=Role.choices,
        required=False,
        default="user",
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
