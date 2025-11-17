from rest_framework import serializers

from apps.users.enums import Role
from apps.users.models import User, Withdrawal
from apps.users.services.admin_users_services import AdminUserService


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


class WithdrawalUserDetailSerializer(serializers.ModelSerializer[User]):
    profile_img_url = serializers.CharField(allow_null=True)
    gender = serializers.CharField()
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    joined_at = serializers.DateTimeField(source="created_at")

    class Meta:
        model = User
        fields = [
            "id",
            "profile_img_url",
            "name",
            "gender",
            "nickname",
            "email",
            "role",
            "status",
            "joined_at",
        ]

    def get_role(self, obj: User) -> str:
        return AdminUserService.get_user_role(obj)

    def get_status(self, obj: User) -> str:
        return AdminUserService.get_user_status(obj)


class WithdrawalInfoSerializer(serializers.ModelSerializer[Withdrawal]):
    id = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField()
    due_date = serializers.DateField()

    class Meta:
        model = Withdrawal
        fields = [
            "id",
            "reason",
            "reason_detail",
            "created_at",
            "due_date",
        ]


class WithdrawalDetailResponseSerializer(serializers.Serializer[dict[str, object]]):
    user = WithdrawalUserDetailSerializer()
    withdrawal = WithdrawalInfoSerializer()
