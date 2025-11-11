from __future__ import annotations

from datetime import date
from typing import Optional

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.views import ExceptionHandledAPIView
from apps.users.enums import Reason
from apps.users.permissions import IsStaffRole
from apps.users.serializers.admin_dashboard_serializers import (
    AdminWithdrawalReasonDistributionResponseSerializer,
    AdminWithdrawalReasonTrendResponseSerializer,
)
from apps.users.services.admin_dashboard_services import AdminDashboardStatsService


class AdminWithdrawalReasonStatsView(ExceptionHandledAPIView):
    """
    어드민 - 회원 탈퇴 사유 추적
    """

    permission_classes = [IsAuthenticated, IsStaffRole]

    @extend_schema(
        tags=["Admin"],
        operation_id="v1_admin_dashboard_withdrawal_reason_stats",
        summary="대시보드 - 회원 탈퇴 사유 추적(월별, 최근 12개월)",
        description="`reason`에 해당하는 탈퇴 사유의 최근 12개월 **월별 건수**를 반환",
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
        responses={200: AdminWithdrawalReasonTrendResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        reason_str = request.query_params.get("reason")
        if not reason_str:
            return Response({"error": "탈퇴 사유 선택은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reason_enum = Reason(reason_str)
        except ValueError:
            return Response({"error": "유효하지 않은 사유입니다."}, status=status.HTTP_400_BAD_REQUEST)

        payload = AdminDashboardStatsService.get_trends(interval="month", reason=reason_enum.value)
        serializer = AdminWithdrawalReasonTrendResponseSerializer(instance=payload)
        return Response(
            {
                "detail": "회원탈퇴 사유 추적 조회에 성공하였습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminWithdrawalReasonStatsAllTimeView(ExceptionHandledAPIView):
    """
    어드민 - 회원 탈퇴 사유 분포
    """

    permission_classes = [IsAuthenticated, IsStaffRole]

    @extend_schema(
        tags=["Admin"],
        operation_id="v1_admin_dashboard_withdrawal_reason_distribution",
        summary="대시보드 - 회원 탈퇴 사유 분포(전체 기간)",
        description="모든 탈퇴 `reason`에 대해 지정 구간(없으면 전체)의 **사유별 분포/비율**을 반환",
        parameters=[
            OpenApiParameter(
                name="date_from",
                required=False,
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="집계 시작일(YYYY-MM-DD). 없으면 전체 기간 시작",
            ),
            OpenApiParameter(
                name="date_to",
                required=False,
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="집계 종료일(YYYY-MM-DD). 없으면 전체 기간 종료",
            ),
        ],
        responses={200: AdminWithdrawalReasonDistributionResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        df = request.query_params.get("date_from")
        dt = request.query_params.get("date_to")

        try:
            date_from: Optional[date] = date.fromisoformat(df) if df else None
            date_to: Optional[date] = date.fromisoformat(dt) if dt else None
        except ValueError:
            return Response({"error": "날짜 형식은 YYYY-MM-DD 입니다."}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.localdate()
        if (date_from and date_from > today) or (date_to and date_to > today):
            return Response({"error": "미래 날짜는 허용되지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        if date_from and date_to and date_from > date_to:
            return Response({"error": "시작일은 종료일보다 이후일 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        payload = AdminDashboardStatsService.get_reason_distribution_all_time(
            date_from=date_from,
            date_to=date_to,
        )

        serializer = AdminWithdrawalReasonDistributionResponseSerializer(instance=payload)
        return Response(
            {
                "detail": "회원 탈퇴 사유 분포 조회에 성공하였습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
