from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.recruitments.models import Application, ApplicationStatus

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()


@dataclass(frozen=True)
class WithdrawResult:
    application_id: int
    status: str


def withdraw_application(*, user: UserModel, application_uuid: str) -> Application:
    """
    지원 취소 비즈니스 로직
    - 본인 소유가 아니면 403
    - 상태가 APPROVED/REJECTED면 400
    - 성공 시 status를 WITHDRAWN으로 변경
    """
    try:
        app: Application = Application.objects.select_for_update().get(uuid=application_uuid)
    except ObjectDoesNotExist:
        raise NotFound({"error": "요청하신 데이터를 찾을 수 없습니다."})

    if app.user_id != user.id:
        raise PermissionDenied({"error": "접근 권한이 없습니다."})

    if app.status in (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED):
        raise ValidationError({"error": "이미 승인되거나 거절된 항목은 취소할 수 없습니다."})

    if app.status == ApplicationStatus.CANCELED:
        raise ValidationError({"error": "이미 취소된 항목입니다."})

    app.status = ApplicationStatus.CANCELED
    app.save(update_fields=["status"])

    return app
