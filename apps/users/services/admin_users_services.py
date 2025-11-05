from typing import Any, Dict

from django.db.models import (
    Case,
    CharField,
    Exists,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
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
        is_withdrawn = User.objects.withdrawal_pending().filter(id=user.id).exists()
        if is_withdrawn:
            return UserStatus.WITHDRAWAL_PENDING.value
        return UserStatus.ACTIVE.value if user.is_active else UserStatus.INACTIVE.value

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

    @staticmethod
    def _base_qs() -> QuerySet[User]:
        latest_withdrawal = (
            Withdrawal.objects.filter(user_id=OuterRef("id")).order_by("-created_at").values("created_at")[:1]
        )
        withdrawal_exists = Withdrawal.objects.filter(user_id=OuterRef("id"))

        return User.objects.annotate(
            # 탈퇴요청일
            withdrawal_requested_at=Subquery(latest_withdrawal),
            # 탈퇴요청 존재 여부
            is_withdrawn=Exists(withdrawal_exists),
            # 권한
            effective_role=Case(
                When(is_superuser=True, then=Value(Role.ADMIN.value)),
                When(is_staff=True, then=Value(Role.STAFF.value)),
                default=Value(Role.USER.value),
                output_field=CharField(),
            ),
            # 상태
            status=Case(
                When(Exists(withdrawal_exists), then=Value(UserStatus.WITHDRAWAL_PENDING.value)),
                When(is_active=True, then=Value(UserStatus.ACTIVE.value)),
                default=Value(UserStatus.INACTIVE.value),
                output_field=CharField(),
            ),
        )

    # 회원 목록 조회

    @staticmethod
    def get_user_list(
        *,
        order: str = "id",
        q: str | None = None,
        role: str | None = None,
        status: str | None = None,
    ) -> QuerySet[User]:
        """
        회원 목록 조회(필터/정렬/페이지네이션 적용)
        """
        qs = AdminUserService._base_qs()

        # 검색: 이메일/닉네임/이름/ID
        if q:
            cond = Q(email__icontains=q) | Q(nickname__icontains=q) | Q(name__icontains=q)
            if q.isdigit():
                cond |= Q(id=int(q))
            qs = qs.filter(cond)

        # ---- 권한별 필터링 ----
        if role:
            r = role.lower()
            if r == Role.ADMIN.value:
                qs = qs.filter(is_superuser=True)
            elif r == Role.STAFF.value:
                qs = qs.filter(is_superuser=False, is_staff=True)
            elif r == Role.USER.value:
                qs = qs.filter(is_superuser=False, is_staff=False)

        # ---- 상태별 필터링 ----
        if status:
            s = status.lower()
            if s == UserStatus.WITHDRAWAL_PENDING.value:
                qs = qs.filter(is_active=False, withdrawals__isnull=False)
            elif s == UserStatus.ACTIVE.value:
                qs = qs.filter(is_active=True)
            elif s == UserStatus.INACTIVE.value:
                qs = qs.filter(is_active=False, withdrawals__isnull=True)

        # ---- 정렬 ----
        return qs.order_by(order)

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
