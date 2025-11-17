from typing import Any, Dict

from rest_framework import serializers


class PasswordResetSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    비밀번호 재설정 시리얼라이저
    """

    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)
