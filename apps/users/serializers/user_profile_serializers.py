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
            "profile_img_url",  # 모델 필드 이름과 일치
            "created_at",
        ]
        read_only_fields = fields


class UserProfileUpdateSerializer(serializers.ModelSerializer[Any]):
    """
    사용자 정보 수정 요청 시리얼라이저
    - 수정 후 사용자 정보를 반환
    """

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
        fields = ("nickname", "profile_img_url", "phone_number", "verify_token")
        extra_kwargs = {"profile_img_url": {"required": False}}


class UserProfileUpdateResponseSerializer(serializers.ModelSerializer[Any]):
    """
    사용자 정보 수정 응답 시리얼라이저
    - 수정 후 사용자 정보를 반환
    """

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "nickname",
            "name",
            "phone_number",
            "birthday",
            "profile_img_url",
            "created_at",
        )


class UserProfilePasswordUpdateSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    내 정보 수정 - 비밀번호 변경
    """

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)
