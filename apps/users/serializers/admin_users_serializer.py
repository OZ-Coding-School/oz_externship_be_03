from typing import TYPE_CHECKING, Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.users.enums import Role, UserStatus
from apps.users.models import User as UserModel
from apps.users.services.admin_users_services import AdminUserService
from apps.users.validators import validate_korean_phone

User = get_user_model()

if TYPE_CHECKING:
    from apps.users.models import User as UserModel


# [관리자] 회원 목록 조회
class AdminUserItemSerializer(serializers.ModelSerializer["UserModel"]):
    # annotate 필드
    status = serializers.CharField(read_only=True)
    role = serializers.CharField(source="effective_role", read_only=True)
    withdrawal_requested_at = serializers.DateTimeField(allow_null=True, required=False, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nickname",
            "name",
            "birthday",
            "status",
            "role",
            "created_at",
            "withdrawal_requested_at",
        ]
        read_only_fields = fields


# [관리자] data: {users: [...]}
class AdminUserListDataSerializer(serializers.Serializer[Dict[str, Any]]):
    users = AdminUserItemSerializer(many=True)
    pagination = serializers.DictField()


# [관리자] detail: "", data: {users: [...]}
class AdminUserListResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    detail = serializers.CharField()
    results = AdminUserListDataSerializer(many=True)

    def to_representation(self, instance: Any) -> Dict[str, Any]:
        rep = super().to_representation(instance)
        return {
            "detail": rep["detail"],
            "data": rep["results"],
        }


# [관리자] 회원 상세 조회
class AdminUserDetailSerializer(serializers.Serializer[UserModel]):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    nickname = serializers.CharField()
    name = serializers.CharField()
    gender = serializers.CharField()
    birthday = serializers.DateField()
    phone_number = serializers.CharField(read_only=True)
    status = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    profile_img_url = serializers.URLField()

    def get_status(self, obj: UserModel) -> str:
        return AdminUserService.get_user_status(obj)

    def get_role(self, obj: UserModel) -> str:
        return AdminUserService.get_user_role(obj)


# [관리자] 회원 정보 수정
class AdminUserUpdateSerializer(serializers.ModelSerializer[UserModel]):

    status = serializers.ChoiceField(choices=UserStatus.choices, required=False)
    phone_number = serializers.CharField(
        validators=[validate_korean_phone], required=False, help_text="휴대폰 번호 (0100000000) 저장 가능"
    )
    profile_img = serializers.ImageField(required=False, allow_empty_file=True)

    class Meta:
        model = User
        fields = [
            "name",
            "gender",
            "nickname",
            "phone_number",
            "status",
            "profile_img",
            "birthday",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}


# [관리자] 회원 정보 수정 응답
class AdminUserUpdateResponseSerializer(serializers.Serializer[UserModel]):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    nickname = serializers.CharField()
    name = serializers.CharField()
    gender = serializers.CharField()
    phone_number = serializers.CharField(read_only=True)
    status = serializers.SerializerMethodField()
    profile_img_url = serializers.URLField()
    updated_at = serializers.DateTimeField()

    def get_status(self, obj: UserModel) -> str:
        return AdminUserService.get_user_status(obj)


# [관리자] 회원 권한 변경 요청
class AdminUserRoleUpdateRequestSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(
        choices=[(r.value, r.name) for r in Role], help_text="변경할 권한 (user | staff | admin)"
    )
