from rest_framework import serializers

from apps.users.enums import Role
from apps.users.models import Withdrawal


class WithdrawalListItemSerializer(serializers.ModelSerializer[Withdrawal]):
    email = serializers.EmailField(source="user.email")
    name = serializers.CharField(source="user.name")
    role = serializers.ChoiceField(
        choices=Role.choices,
        read_only=True,
        help_text="user|staff|superuser (기본값: user)",
    )
    birthday = serializers.DateField(source="user.birthday")
    withdrawn_at = serializers.DateTimeField(source="created_at")

    class Meta:
        model = Withdrawal
        fields = [
            "id",
            "email",
            "name",
            "role",
            "birthday",
            "reason",
            "withdrawn_at",
        ]
