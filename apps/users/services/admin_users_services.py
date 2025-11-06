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

from apps.core.exceptions import Conflict
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
        """
        중복 검사 포함 (nickname, phone_number)
        """
        nickname = update_data.get("nickname")
        phone_number = update_data.get("phone_number")

        # --- 중복 검사 ---
        dup_q = Q()
        if nickname is not None:
            dup_q |= Q(nickname__iexact=nickname)
        if phone_number is not None:
            dup_q |= Q(phone_number=phone_number)

        if dup_q:
            exists = User.objects.filter(dup_q).exclude(id=user.id).values("nickname", "phone_number")[:1]
            if exists:
                fields: list[str] = []
                if nickname is not None and User.objects.filter(nickname__iexact=nickname).exclude(id=user.id).exists():
                    fields.append("닉네임")
                if (
                    phone_number is not None
                    and User.objects.filter(phone_number=phone_number).exclude(id=user.id).exists()
                ):
                    fields.append("휴대폰 번호")
                field_msg = " 및 ".join(fields) if fields else "항목"
                raise Conflict({"error": f"이미 사용 중인 {field_msg}입니다."})

        # --- 이전 값과 다른 새 값만 반영 ---
        update_fields: list[str] = []
        for field, value in update_data.items():
            if not hasattr(user, field):
                continue
            if getattr(user, field) != value:
                setattr(user, field, value)
                update_fields.append(field)

        if not update_fields:
            return user

        user.save(update_fields=update_fields)
        return user

    # 회원 권한 변경
    @staticmethod
    def change_user_role(user: User, new_role: str) -> User:
        """
        사용 가능한 Role Enum 값: ADMIN, STAFF, USER
        """
        role_enum: Role
        if isinstance(new_role, Role):
            role_enum = new_role
        else:
            try:
                role_enum = Role[new_role.upper()]
            except KeyError:
                raise ValueError(f"지원하지 않는 권한입니다. 사용 가능한 값: {[r.name for r in Role]}")

        target_is_superuser = role_enum == Role.ADMIN
        target_is_staff = role_enum in (Role.ADMIN, Role.STAFF)

        # 이전 권한과 같으면 변경 생략
        if user.is_superuser == target_is_superuser and user.is_staff == target_is_staff:
            return user

        user.is_superuser = target_is_superuser
        user.is_staff = target_is_staff
        user.save(update_fields=["is_superuser", "is_staff"])
        return user

    # 회원 삭제
    @staticmethod
    def delete_user(user: User) -> None:
        user.delete()
