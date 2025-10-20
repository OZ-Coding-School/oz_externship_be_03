from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.users.validators import validate_korean_phone, validate_nickname

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer[Any]):
    """
    내 정보 조회 Serializer
    - 로그인된 사용자 정보 반환
    - 비밀번호, 관리자 여부 등은 제외
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nickname",
            "name",
            "phone_number",
            "birthday",
            "profile_image_url",
            "created_at",
        ]
        read_only_fields = fields


class UserProfileUpdateSerializer(serializers.ModelSerializer[Any]):
    verify_token = serializers.CharField(write_only=True, required=False)
    nickname = serializers.CharField(
        required=False,
        validators=[validate_nickname],
    )
    phone_number = serializers.CharField(
        required=False,
        validators=[
            validate_korean_phone,
            UniqueValidator(queryset=User.objects.all(), message="이미 사용 중인 휴대폰 번호입니다."),
        ],
    )

    class Meta:
        model = User
        fields = ("nickname", "profile_image_url", "phone_number", "verify_token")
        extra_kwargs = {"profile_image_url": {"required": False}}


class UserProfilePasswordUpdateSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    내 정보 수정 - 비밀번호 변경
    """

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

