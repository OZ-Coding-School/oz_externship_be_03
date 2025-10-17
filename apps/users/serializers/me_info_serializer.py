from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

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
