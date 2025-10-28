from typing import Any

from rest_framework import serializers

from apps.users.enums import Role, UserStatus
from apps.users.models import User
from apps.users.services.admin_users_services import AdminUserService


# [관리자] 회원 목록 조회
class AdminUserListSerializer(serializers.ModelSerializer[User]):

    role = serializers.ChoiceField(choices=Role.choices, read_only=True)
    withdrawal_requested_at = serializers.DateTimeField(read_only=True, allow_null=True)
    status = serializers.ChoiceField(choices=UserStatus.choices, read_only=True)

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

    role: serializers.CharField = serializers.CharField(help_text="변경할 권한 (user | staff | admin)")

    def validate_role(self, value: str) -> str:
        # 입력된 권한값 검증 (대소문자 무관)
        normalized = value.lower()
        valid_roles = [r for r in Role]

        if normalized not in valid_roles:
            raise serializers.ValidationError("유효하지 않은 권한입니다.")

        return normalized


# [관리자] 회원 권한 변경 응답
class AdminUserRoleUpdateResponseSerializer(serializers.Serializer[Any]):

    role = serializers.ChoiceField(choices=Role.choices, read_only=True)
    detail = serializers.CharField(default="회원 권한이 변경되었습니다.")

    class Meta:
        model = User
        fields = [
            "detail",
            "id",
            "email",
            "name",
            "role",
            "updated_at",
        ]
