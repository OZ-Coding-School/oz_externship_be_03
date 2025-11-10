from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.views import ExceptionHandledAPIView
from apps.users.enums import Reason
from apps.users.permissions import IsStaffRole
from apps.users.services.admin_dashboard_services import AdminDashboardStatsService


class AdminWithdrawalReasonStatsView(ExceptionHandledAPIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    @extend_schema(
        tags=["Admin"],
        operation_id="v1_admin_dashboard_withdrawal_reason_stats",
        summary="대시보드 - 회원 탈퇴 사유 추적",
        description="`reason`에 해당하는 탈퇴 사유의 최근 12개월 월별 통계를 반환",
        parameters=[
            OpenApiParameter(
                name="reason",
                required=True,
                type=OpenApiTypes.STR,
                enum=[r.value for r in Reason],
                location=OpenApiParameter.QUERY,
                description="탈퇴 사유 코드",
            ),
        ],
        responses={
            200: OpenApiResponse(description="성공적으로 월별 통계를 반환"),
            400: OpenApiResponse(description="요청 파라미터 오류"),
            403: OpenApiResponse(description="관리자 권한 필요"),
        },
    )
    def get(self, request: Request) -> Response:
        reason_str = request.query_params.get("reason")
        if not reason_str:
            return Response({"error": "탈퇴 사유 선택은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reason_enum = Reason(reason_str)
        except ValueError:
            return Response({"error": "유효하지 않은 사유입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 2) 최근 12개월, 해당 사유만
        result = AdminDashboardStatsService.get_trends(interval="month", reason=reason_enum.value)

        payload = {
            "detail": "회원탈퇴 사유 추적 조회에 성공하였습니다.",
            "data": {
                "interval": result.interval,
                "from_date": result.date_from,
                "to_date": result.date_to,
                "total_withdrawals": result.total,
                "items": [{"period": i.period, "count": i.count} for i in result.items],
            },
        }
        return Response(payload, status=status.HTTP_200_OK)
