from typing import Any, Dict

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import (
    NotFound,
    ValidationError,
)

from apps.users.models import User, Withdrawal


class AdminWithdrawalService:
    """관리자 탈퇴 회원 관련 서비스"""

    @staticmethod
    def get_withdrawal_detail(user_id: int) -> Dict[str, Any]:
        """
        탈퇴 회원 상세 정보 조회
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound("회원 정보를 찾을 수 없습니다.")

        base_qs: QuerySet[Withdrawal] = Withdrawal.objects.select_related("user").filter(user_id=user_id)

        today = timezone.localdate()

        # '유예기간 내' 이력 우선, 없으면 최신 이력
        withdrawal = (
            base_qs.filter(due_date__gte=today).order_by("-created_at").first()
            or base_qs.order_by("-created_at").first()
        )

        if not withdrawal:
            raise ValidationError({"error": "탈퇴 이력이 없습니다."})

        return {
            "user": user,
            "withdrawal": withdrawal,
        }
