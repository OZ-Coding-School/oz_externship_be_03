from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

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

    nickname = serializers.CharField(
        required=False,
        validators=[validate_nickname],
    )
    phone_number = serializers.CharField(
        required=False,
        validators=[validate_korean_phone],
    )
    phone_verify_token = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ("nickname", "profile_img_url", "phone_number", "phone_verify_token")
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


class DupNicknameQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """
    닉네임 중복 확인 쿼리 파라미터
    """

    nickname = serializers.CharField(max_length=10, min_length=1, required=True, trim_whitespace=True)
    case_insensitive = serializers.BooleanField(required=False, default=True)


class DupNicknameDataSerializer(serializers.Serializer[dict[str, Any]]):
    """
    닉네임 중복 응답 data 필드 스키마
    """

    nickname = serializers.CharField()
    available = serializers.BooleanField()


class DupNicknameResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """
    닉네임 중복 전체 응답 스키마
    """

    detail = serializers.CharField()
    payload = DupNicknameDataSerializer(source="data")
