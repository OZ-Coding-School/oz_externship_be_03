from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.withdrawal_trends_serializers import (
    WithdrawalTrendsDataSerializer,
)
from apps.users.services.withdrawal_trends_services import get_withdrawal_trends


class WithdrawalTrendsAPIView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Admin"],
        summary="대시보드 - 회원 탈퇴 추세",
        description="관리자가 월별(최근 12개월)/연별(최근 5년) 탈퇴 추세를 확인합니다.",
        responses=inline_serializer(
            name="WithdrawalTrendsData",
            fields={
                "detail": serializers.CharField(),
                "data": WithdrawalTrendsDataSerializer(),
            },
        ),
        parameters=[
            OpenApiParameter(
                name="interval",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="통계 구간 - 월간(month), 연간(year) / 미입력시 month가 기본",
            )
        ],
    )
    def get(self, request: Request) -> Response:
        interval = request.query_params.get("interval", "month")
        if interval not in ("month", "year"):
            return Response(
                {"error": "interval 파라미터는 'month' 또는 'year'만 허용됩니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = get_withdrawal_trends(interval=interval)  # type: ignore[arg-type]
        serializer = WithdrawalTrendsDataSerializer(
            {
                "interval": result["interval"],
                "from": result["from_"],
                "to": result["to"],
                "total_withdrawals": result["total_withdrawals"],
                "items": result["items"],
            }
        )

        return Response(
            {
                "detail": "탈퇴 통계 조회에 성공하였습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
