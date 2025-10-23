from datetime import timedelta
from typing import TYPE_CHECKING, Mapping, Union, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import BadRequest
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.users.enums import Reason
from apps.users.models import Withdrawal

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()

DELETE_GRACE_DAYS = 14


def _to_reason(code: Union[str, Reason]) -> Reason:
    # 방어적으로 문자열을 enum으로 변환
    if isinstance(code, Reason):
        return code
    try:
        return Reason(code)
    except Exception:
        raise BadRequest({"error": "유효하지 않은 탈퇴 사유입니다."})


@transaction.atomic
def withdraw(*, user: "UserModel", reason: str, reason_detail: str) -> None:
    """
    회원 탈퇴 절차
    - is_active=False
    - withdrawal 레코드 생성
    - 서버사이드 로그아웃
    """
    if not user.is_active:
        raise BadRequest({"error": "이미 탈퇴 처리된 계정입니다."})

    reason_enum = _to_reason(reason)

    # 중복 요청 방지 (조건부 유니크 제약 또는 추가 검사)
    if Withdrawal.objects.filter(user=user).exists():
        raise BadRequest({"error": "이미 탈퇴 요청이 존재합니다."})

    due_date = timezone.now().date() + timedelta(days=DELETE_GRACE_DAYS)

    Withdrawal.objects.create(
        user=user,
        reason=reason_enum,
        reason_detail=reason_detail,
        due_date=due_date,
    )

    user.is_active = False
    user.save(update_fields=["is_active"])


@transaction.atomic
def recover_account(*, claims: Mapping[str, object]) -> None:
    """
    퍼미션에서 이미 verify_and_consume() 완료된 클레임만 받아 복구 처리
    """
    sub = claims.get("sub")
    user = User.objects.filter(email=sub).first()
    if user is None:
        raise NotFound({"error": "해당 이메일의 사용자를 찾을 수 없습니다."})

    wd = Withdrawal.objects.filter(user=user).order_by("-created_at").first()
    if wd is None:
        raise NotFound({"error": "복구 가능한 탈퇴 요청이 존재하지 않습니다."})

    user.is_active = True
    user.save(update_fields=["is_active"])
    wd.delete()
