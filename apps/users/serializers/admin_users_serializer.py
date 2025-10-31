from typing import Any, Dict

from rest_framework import serializers

from apps.users.enums import Role, UserStatus
from apps.users.models import User
from apps.users.services.admin_users_services import AdminUserService
from apps.users.validators import validate_korean_phone


# [관리자] 회원 목록 조회
class AdminUserItemSerializer(serializers.Serializer[Dict[str, Any]]):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    nickname = serializers.CharField()
    name = serializers.CharField()
    birthday = serializers.DateField()
    status = serializers.ChoiceField(choices=UserStatus.choices)
    role = serializers.ChoiceField(choices=Role.choices)
    created_at = serializers.DateTimeField()
    withdrawal_requested_at = serializers.DateTimeField(allow_null=True, required=False)

    @staticmethod
    def from_user(user: User) -> Dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "nickname": user.nickname,
            "name": user.name,
            "birthday": user.birthday,
            "status": str(AdminUserService.get_user_status(user)),
            "role": (
                Role.ADMIN.value if user.is_superuser else (Role.STAFF.value if user.is_staff else Role.USER.value)
            ),
            "created_at": user.created_at,
            "withdrawal_requested_at": getattr(user, "withdrawal_requested_at", None),
        }


# [관리자] data: {users: [...]}
class AdminUserListDataSerializer(serializers.Serializer[Dict[str, Any]]):
    users = AdminUserItemSerializer(many=True)


# [관리자] detail: data: {{users: [...]}}
class AdminUserListResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    detail = serializers.CharField()
    payload = AdminUserListDataSerializer()

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        base = super().to_representation(instance)
        payload = base.pop("payload", {})
        base["data"] = payload
        return base


# [관리자] 회원 상세 조회
class AdminUserDetailSerializer(serializers.ModelSerializer[User]):

    status: serializers.SerializerMethodField = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "nickname",
            "birthday",
            "phone_number",
            "is_active",
            "is_staff",
            "is_superuser",
            "status",
            "created_at",
            "profile_img_url",
        ]

    def get_status(self, obj: User) -> str:
        # 상태값을 문자열로 반환
        return str(AdminUserService.get_user_status(obj))


# [관리자] 회원 정보 수정
class AdminUserUpdateSerializer(serializers.ModelSerializer[User]):

    status = serializers.ChoiceField(choices=UserStatus.choices, required=False)
    phone_number = serializers.CharField(
        validators=[validate_korean_phone], required=False, help_text="휴대폰 번호 (0100000000) 저장 가능"
    )

    class Meta:
        model = User
        fields = [
            "name",
            "gender",
            "nickname",
            "phone_number",
            "status",
            "profile_img_url",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}


# [관리자] 회원 삭제 응답
class AdminUserDeleteResponseSerializer(serializers.Serializer[Any]):

    detail = serializers.CharField(help_text="삭제 완료 메시지")


# [관리자] 회원 권한 변경 요청
class AdminUserRoleUpdateRequestSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(
        choices=[(r.value, r.name) for r in Role], help_text="변경할 권한 (user | staff | admin)"
    )


# [관리자] 회원 권한 변경 응답
class AdminUserRoleUpdateResponseSerializer(serializers.Serializer[Any]):

    role = serializers.ChoiceField(choices=Role.choices, read_only=True)
    detail = serializers.CharField(default="회원 권한이 변경되었습니다.")

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "role",
            "updated_at",
        ]
