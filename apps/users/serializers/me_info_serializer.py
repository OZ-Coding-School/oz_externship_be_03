from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

User = get_user_model()


class MeInfoSerializer(serializers.ModelSerializer[Any]):
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


class MeInfoUpdateSerializer(serializers.ModelSerializer[Any]):
    verify_token = serializers.CharField(write_only=True, required=False)
    nickname = serializers.CharField(required=False)
    phone_number = serializers.CharField(
        required=False,
        validators=[
            UniqueValidator(queryset=User.objects.all(), message="이미 사용 중인 휴대폰 번호입니다."),
        ],
    )

    class Meta:
        model = User
        fields = ("nickname", "profile_image_url", "phone_number", "verify_token")
        extra_kwargs = {"profile_image_url": {"required": False}}

    def validate(self, attrs: Dict[str, Any]) -> Any:
        if "phone_number" in attrs and not attrs.get("verify_token"):
            raise serializers.ValidationError({"verify_token": "휴대폰 번호 변경에는 verify_token이 필요합니다."})
        return attrs
