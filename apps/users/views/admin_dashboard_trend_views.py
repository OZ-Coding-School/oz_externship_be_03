from __future__ import annotations

from typing import Any, Callable, ClassVar, Dict, Protocol, Type, TypeVar, cast

from drf_spectacular.utils import F, OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.admin_dashboard_trend_serializers import (
    SignupTrendsDataSerializer,
    WithdrawalTrendsDataSerializer,
)
from apps.users.services.admin_dashboard_trend_services import (
    Interval,
    TrendResult,
    get_signup_trends,
    get_withdrawal_trends,
)


class TrendsService(Protocol):
    def __call__(self, *, interval: Interval) -> TrendResult: ...


# 제네릭 데코레이터 타입 변수
_F = TypeVar("_F", bound=Callable[..., Any])


def dashboard_trend_schema(
    *,
    summary: str,
    description: str,
    data_serializer: Type[serializers.Serializer[Dict[str, Any]]],
) -> Callable[[_F], _F]:
    """
    대시보드 추세 API 공통 extend_schema 데코레이터
    """
    return extend_schema(
        tags=["Admin"],
        summary=summary,
        description=description,
        responses=inline_serializer(
            name="TrendResponse",
            fields={"detail": serializers.CharField(), "data": data_serializer()},
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


class BaseTrendsAPIView(APIView):
    """
    공통 View:
    - interval query 파싱/검증
    - 서비스 호출(get_*_trends)
    - 공통 total → 각 Serializer의 total_* 필드명으로 매핑
    """

    permission_classes = [IsAdminUser]

    # 서브클래스에서 지정해야 하는 것들
    data_serializer_class: Type[serializers.Serializer[Dict[str, Any]]]
    service_func: ClassVar[TrendsService]
    total_key_name: str

    def _serialize_payload(self, result: TrendResult) -> Dict[str, Any]:
        """
        공통 result(total, items, interval, from_date, to_date)
        각 Serializer가 기대하는 total_* 키 이름으로 변환
        """
        payload = {
            "interval": result["interval"],
            "from_date": result["from_date"],
            "to_date": result["to_date"],
            self.total_key_name: result["total"],
            "items": result["items"],
        }
        serializer = self.data_serializer_class(payload)
        return serializer.data

    def get(self, request: Request) -> Response:
        raw = request.query_params.get("interval", "month")
        if raw not in ("month", "year"):
            return Response(
                {"error": "interval 파라미터는 'month' 또는 'year'만 허용됩니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        interval: Interval = cast(Interval, raw)

        # 클래스에서 꺼내 호출 → 바인딩 없음, 키워드 인자 사용
        result = type(self).service_func(interval=interval)
        data = self._serialize_payload(result)
        return Response({"detail": "통계 조회에 성공하였습니다.", "data": data}, status=status.HTTP_200_OK)


# ----- 탈퇴 추세 -----
class WithdrawalTrendsAPIView(BaseTrendsAPIView):
    data_serializer_class = WithdrawalTrendsDataSerializer
    service_func: ClassVar[TrendsService] = get_withdrawal_trends
    total_key_name = "total_withdrawals"

    @dashboard_trend_schema(
        summary="대시보드 - 회원 탈퇴 추세",
        description="관리자가 월별(최근 12개월)/연별(최근 5년) 탈퇴 추세를 확인합니다.",
        data_serializer=data_serializer_class,
    )
    def get(self, request: Request) -> Response:
        return super().get(request)


# ----- 가입 추세 -----
class SignupTrendsAPIView(BaseTrendsAPIView):
    data_serializer_class = SignupTrendsDataSerializer
    service_func: ClassVar[TrendsService] = get_signup_trends
    total_key_name = "total_signups"

    @dashboard_trend_schema(
        summary="대시보드 - 회원 가입 추세",
        description="관리자가 월별(최근 12개월)/연별(최근 5년) 가입 추세를 확인합니다.",
        data_serializer=data_serializer_class,
    )
    def get(self, request: Request) -> Response:
        return super().get(request)
