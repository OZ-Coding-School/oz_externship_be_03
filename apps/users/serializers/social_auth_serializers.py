from __future__ import annotations

from typing import Any

from rest_framework import serializers


class SocialAuthRequestSerializer(serializers.Serializer[Any]):  # ✅ 제네릭 타입 지정
    """소셜 로그인 요청용 (카카오 / 네이버)"""

    code = serializers.CharField(required=True, help_text="OAuth 인가 코드")
    state = serializers.CharField(required=False, allow_blank=True, help_text="네이버 로그인 시 전달되는 state 값")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:  # ✅ 타입 명시
        if not attrs.get("code"):
            raise serializers.ValidationError({"error": "요청 형식이 올바르지 않습니다. code는 필수값입니다."})
        return attrs
