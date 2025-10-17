from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()


class EmailLookupSerializer(serializers.ModelSerializer[Any]):
    """
    아이디(이메일) 찾기 Serializer
    - User 모델 기반
    - 이메일만 반환 (마스킹 처리된 값)
    """

    email = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["email"]

    def get_email(self, obj: UserModel) -> str:
        """
        이메일 마스킹 처리
        예: kimkim@gmail.com → k****m@gmail.com
        """
        email = obj.email
        name, domain = email.split("@", 1)
        if len(name) <= 1:
            masked_name = name
        elif len(name) == 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + ("*" * (len(name) - 2)) + name[-1]

        return f"{masked_name}@{domain}"
