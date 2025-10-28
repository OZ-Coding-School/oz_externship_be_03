from typing import Any, Dict

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from apps.users.enums import Role, UserStatus
from apps.users.models import User, Withdrawal


class AdminUserService:

    # 회원 목록 조회

    @staticmethod
    def get_user_list() -> QuerySet[User]:
        return User.objects.all().order_by("-created_at")

    # 회원 상세 조회

    @staticmethod
    def get_user_detail(user_id: int) -> User:
        return get_object_or_404(User, id=user_id)

    # 회원 정보 수정

    @staticmethod
    def update_user_info(user_id: int, update_data: Dict[str, Any]) -> User:
        user = get_object_or_404(User, id=user_id)
        for field, value in update_data.items():
            setattr(user, field, value)
        user.save()
        return user

    # 회원 권한 변경 (Role Enum 기반)

    @staticmethod
    def change_user_role(user_id: int, new_role: str) -> User:

        user = get_object_or_404(User, id=user_id)

        # 문자열로 들어올 수 있으므로 Enum으로 안전 변환
        if isinstance(new_role, str):
            try:
                new_role = Role[new_role.upper()]  # "staff" / "STAFF" 둘 다 허용
            except KeyError:
                raise ValueError(f"지원하지 않는 권한입니다: {new_role}")

        # 권한에 따른 필드 설정
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
            raise ValueError(f"지원하지 않는 권한입니다: {new_role}")

        user.save()
        return user

    # 회원 삭제

    @staticmethod
    def delete_user(user_id: int) -> None:
        user = get_object_or_404(User, id=user_id)
        user.delete()

    # 회원 상태 계산

    @staticmethod
    def get_user_status(user: User) -> UserStatus:
        """
        외원 상태 조회
        ACTLVE - 활성
        INACTIVE - 비활성
        WITHDRAWAL_PEDING - 탈퇴요청
        """

        has_withdrawal = Withdrawal.objects.filter(user_id=user.id).exists()

        if has_withdrawal:
            # 탈퇴 테이블에 있으면 탈퇴 요청 중
            return UserStatus.WITHDRAWAL_PENDING

        # 탈퇴 테이블에 없고 활성 상태면 정상
        if user.is_active:
            return UserStatus.ACTIVE

        # 탈퇴 테이블에 없고 비활성이면 완전 탈퇴
        return UserStatus.INACTIVE