from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Literal, Optional, TypedDict, cast

from django.db.models import Count
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone

from apps.users.models import Withdrawal

Interval = Literal["month", "year"]


class _Row(TypedDict):
    period: date | datetime
    count: int


def _fmt(p: date | datetime, fmt: str) -> str:
    """period 문자열로 변환."""
    d = p.date() if isinstance(p, datetime) else p
    return d.strftime(fmt)


# ------------------------------------------------------
# 응답 형태
# ------------------------------------------------------
@dataclass
class TrendItem:
    period: str
    count: int


@dataclass
class TrendResult:
    """
    ---------------------------------------------------------
    - interval : "month"|"year"
    - date_from: 포함 시작일
    - date_to  : 포함 종료일(말일/연말 기준)
    - total    : 모든 구간 count 합계
    - items    : 기간별 데이터 리스트
    ---------------------------------------------------------
    """

    interval: Interval
    date_from: str
    date_to: str
    total: int
    items: List[TrendItem]


# ------------------------------------------------------
# 서비스
# ------------------------------------------------------
class AdminDashboardStatsService:
    """
    ---------------------------------------------------------
    # 최근 12개월 탈퇴 사유 전체 집계
    result = AdminDashboardStatsService.get_trends("month")

    # 최근 12개월 특정 사유 집계
    result = AdminDashboardStatsService.get_trends("month", reason="SPAM")

    # 최근 5년 전체 집계
    result = AdminDashboardStatsService.get_trends("year")
    ---------------------------------------------------------
    """

    @staticmethod
    def get_trends(interval: Interval, reason: Optional[str] = None) -> TrendResult:
        today = timezone.localdate()

        # =====================================================
        # 최근 12개월 월간 통계
        # =====================================================
        if interval == "month":
            months: List[date] = []
            base = date(today.year, today.month, 1)
            for i in range(11, -1, -1):
                y = base.year + (base.month - 1 - i) // 12
                m = (base.month - 1 - i) % 12 + 1
                months.append(date(y, m, 1))

            start = months[0]
            # 다음달의 월초
            last = months[-1]
            end = date(last.year + (1 if last.month == 12 else 0), (last.month % 12) + 1, 1)

            # 탈퇴 요청일 쿼리 및 탈퇴 사유 필터링
            qs = Withdrawal.objects.filter(created_at__date__gte=start, created_at__date__lt=end)
            if reason:
                qs = qs.filter(reason=reason)

            rows: List[_Row] = cast(
                List[_Row],
                list(qs.annotate(period=TruncMonth("created_at")).values("period").annotate(count=Count("id"))),
            )

            counts = {_fmt(r["period"], "%Y-%m"): r["count"] for r in rows}

            # 누락 월은 0으로 채움
            items = [TrendItem(period=m.strftime("%Y-%m"), count=counts.get(m.strftime("%Y-%m"), 0)) for m in months]

            last_day = monthrange(last.year, last.month)[1]
            human_to = date(last.year, last.month, last_day)

            return TrendResult(
                interval="month",
                date_from=start.strftime("%Y-%m-%d"),
                date_to=human_to.strftime("%Y-%m-%d"),
                total=sum(i.count for i in items),
                items=items,
            )

        # =====================================================
        # 최근 5년 연간 통계
        # =====================================================
        years = [today.year - i for i in range(4, -1, -1)]  # 오름차순
        start = date(years[0], 1, 1)
        end = date(years[-1] + 1, 1, 1)

        qs = Withdrawal.objects.filter(created_at__date__gte=start, created_at__date__lt=end)
        if reason:
            qs = qs.filter(reason=reason)

        rows = cast(
            List[_Row],
            list(qs.annotate(period=TruncYear("created_at")).values("period").annotate(count=Count("id"))),
        )

        counts = {_fmt(r["period"], "%Y"): r["count"] for r in rows}

        items = [TrendItem(period=str(y), count=counts.get(str(y), 0)) for y in years]

        human_to = date(years[-1], 12, 31)

        return TrendResult(
            interval="year",
            date_from=start.strftime("%Y-%m-%d"),
            date_to=human_to.strftime("%Y-%m-%d"),
            total=sum(i.count for i in items),
            items=items,
        )
