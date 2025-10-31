from typing import Any, Dict

from rest_framework import serializers

from apps.users.models import User

# 1. 요청 (Request)


class SocialAuthRequestSerializer(serializers.Serializer[Dict[str, Any]]):

    provider = serializers.ChoiceField(choices=[("kakao", "Kakao"), ("naver", "Naver")])
    access_token = serializers.CharField(required=False)
    code = serializers.CharField(required=False)
    state = serializers.CharField(required=False)

    # 최소한의 값 체크만 (형식 위주)
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        provider = data.get("provider")
        if provider not in ["kakao", "naver"]:
            raise serializers.ValidationError({"provider": "지원하지 않는 provider입니다."})
        return data


# 2. 사용자 정보 (User)


class SocialUserSerializer(serializers.ModelSerializer[User]):

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "nickname",
            "phone_number",
            "birthday",
            "gender",
            "profile_img_url",
            "is_active",
            "is_staff",
            "is_superuser",
        ]


# 3. 응답 데이터 구조


class SocialLoginDataSerializer(serializers.Serializer[Dict[str, Any]]):

    user = SocialUserSerializer()
    access_token = serializers.CharField()
    token_type = serializers.CharField()
    access_token_expires_in = serializers.IntegerField()


class SocialLoginResponseSerializer(serializers.Serializer[Dict[str, Any]]):

    detail = serializers.CharField()
    result = SocialLoginDataSerializer()
