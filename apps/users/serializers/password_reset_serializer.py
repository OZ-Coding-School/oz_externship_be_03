from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework import serializers

User = get_user_model()


class PasswordResetSerializer(serializers.ModelSerializer[Any]):
    """
    비밀번호 재설정 시리얼라이저
    - 입력값 일치 검증만 수행
    - 실제 정책 검증 및 토큰 검증은 service에서 수행
    """

    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    _user: AbstractBaseUser | None = None

    class Meta:
        model = User
        fields = ["new_password", "new_password_confirm"]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        pw = attrs.get("new_password")
        pw2 = attrs.get("new_password_confirm")

        if pw != pw2:
            raise serializers.ValidationError({"error": "비밀번호 확인이 일치하지 않습니다."})

        user = self.context.get("user")
        if user is None:
            raise serializers.ValidationError({"error": "내부 오류: user context 누락"})

        self._user = user
        return attrs

    def save(self, **kwargs: Any) -> AbstractBaseUser:
        if self._user is None:
            raise serializers.ValidationError({"error": "내부 오류: 검증 단계가 선행되지 않았습니다."})

        user = self._user
        new_password = self.validated_data["new_password"]

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user
