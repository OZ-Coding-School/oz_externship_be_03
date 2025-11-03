from typing import Any, Dict

from django.db.models import OuterRef, QuerySet, Subquery
from django.shortcuts import get_object_or_404

from apps.users.enums import Role, UserStatus
from apps.users.models import User, Withdrawal


class AdminUserService:
    # 회원 상태 계산
    @staticmethod
    def get_user_status(user: User) -> str:
        """
        회원 상태 조회
        ACTLVE - 활성
        INACTIVE - 비활성
        WITHDRAWAL_PEDING - 탈퇴요청
        """
        has_withdrawal = Withdrawal.objects.filter(user_id=user.id).exists()

        if has_withdrawal:
            # 탈퇴 테이블에 있으면 탈퇴 요청 중
            return UserStatus.WITHDRAWAL_PENDING.value

        # 탈퇴 테이블에 없고 활성 상태면 정상
        if user.is_active:
            return UserStatus.ACTIVE.value

        # 탈퇴 테이블에 없고 비활성이면 완전 탈퇴
        return UserStatus.INACTIVE.value

    @staticmethod
    def get_user_role(user: User) -> str:
        """
        유저 권한 계산
        """
        if user.is_superuser:
            return Role.ADMIN.value
        if user.is_staff:
            return Role.STAFF.value
        return Role.USER.value

    # 회원 목록 조회

    @staticmethod
    def get_user_list() -> QuerySet[User]:
        latest_withdrawal = (
            Withdrawal.objects.filter(user_id=OuterRef("id")).order_by("-created_at").values("created_at")[:1]
        )

        return User.objects.annotate(withdrawal_requested_at=Subquery(latest_withdrawal)).order_by("-created_at")

    # 회원 상세 조회

    @staticmethod
    def get_user(user_id: int) -> User:
        return get_object_or_404(User, id=user_id)

    # 회원 정보 수정

    @staticmethod
    def update_user_info(user: User, update_data: Dict[str, Any]) -> User:
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        user.save()
        return user

    @staticmethod
    def change_user_role(user: User, new_role: str) -> User:
        """
        사용 가능한 Role Enum 값: ADMIN, STAFF, USER
        """
        if isinstance(new_role, str):
            try:
                new_role = Role[new_role.upper()]
            except KeyError:
                raise ValueError(f"지원하지 않는 권한입니다. 사용 가능한 값: {[r.name for r in Role]}")

        # 권한 변경 로직
        if new_role == Role.ADMIN:
            user.is_superuser = True
            user.is_staff = True
        elif new_role == Role.STAFF:
            user.is_superuser = False
            user.is_staff = True
        elif new_role == Role.USER:
            user.is_superuser = False
            user.is_staff = False
        else:
            raise ValueError(f"지원하지 않는 권한입니다. 사용 가능한 값: admin,staff,user")

        user.save()
        return user

    # 회원 삭제

    @staticmethod
    def delete_user(user: User) -> None:
        user.delete()
