from typing import TYPE_CHECKING, Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()


class FindEmailSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    아이디(이메일) 찾기 응답 전용 Serializer
    """

    email = serializers.CharField()

    def to_representation(self, obj: dict[str, str]) -> dict[str, str]:
        """
        응답 직렬화 시점에 이메일 마스킹 처리
        예: kimkim@gmail.com → k****m@gmail.com
        """
        data = super().to_representation(obj)
        email = data.get("email", "")

        if "@" not in email:
            return data  # 안전하게

        name, domain = email.split("@", 1)

        if len(name) <= 1:
            masked_name = name
        elif len(name) == 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + ("*" * (len(name) - 2)) + name[-1]

        data["email"] = f"{masked_name}@{domain}"
        return data
