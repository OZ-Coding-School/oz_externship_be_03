from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from typing import (
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    cast,
)

from django.db.models import Count
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone

from apps.users.enums import Reason
from apps.users.models import Withdrawal

Interval = Literal["month", "year", "all_time"]


class BaseItem(Protocol):
    count: int


class _Row(TypedDict):
    period: date | datetime
    count: int


def _fmt(p: date | datetime, fmt: str) -> str:
    """period 문자열로 변환."""
    d = p.date() if isinstance(p, datetime) else p
    return d.strftime(fmt)


TItem = TypeVar("TItem", bound=BaseItem)


# ------------------------------------------------------
# 응답 형태
# ------------------------------------------------------
@dataclass
class TrendItem:
    period: str
    count: int


@dataclass
class ReasonItem:
    reason_code: str
    reason_label: str
    count: int
    percentage: float


@dataclass
class TrendResult(Generic[TItem]):
    """
    ---------------------------------------------------------
    - interval : "month"|"year"|"all_time"
    - from_date: 포함 시작일
    - to_date  : 포함 종료일(말일/연말 기준)
    - total_withdrawals : 집계 구간 총 탈퇴 수
    - items    : 데이터 리스트(월/연 집계 or 사유별 분포)
    ---------------------------------------------------------
    """

    interval: Interval
    from_date: str
    to_date: str
    total_withdrawals: int
    items: List[TItem]


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

    # 전체 기간 사유별 분포
    result = AdminDashboardStatsService.get_reason_distribution_all_time()
    ---------------------------------------------------------
    """

    @staticmethod
    def get_trends(interval: Interval, reason: Optional[str] = None) -> TrendResult[TrendItem]:
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
                from_date=start.strftime("%Y-%m-%d"),
                to_date=human_to.strftime("%Y-%m-%d"),
                total_withdrawals=sum(i.count for i in items),
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
            from_date=start.strftime("%Y-%m-%d"),
            to_date=human_to.strftime("%Y-%m-%d"),
            total_withdrawals=sum(i.count for i in items),
            items=items,
        )

    @staticmethod
    def get_reason_distribution_all_time(
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> TrendResult[ReasonItem]:
        """
        전체 기간(혹은 지정 범위)에서 탈퇴 사유별 집계 및 퍼센트
        """
        base_qs = Withdrawal.objects.all()

        # 데이터가 전혀 없으면 전체 0카운트로
        if not base_qs.exists():
            today = timezone.localdate()
            return TrendResult(
                interval="all_time",
                from_date=str(today),
                to_date=str(today),
                total_withdrawals=0,
                items=[
                    ReasonItem(
                        reason_code=m.value,
                        reason_label=m.label,
                        count=0,
                        percentage=0.0,
                    )
                    for m in Reason
                ],
            )

        # 조회 시작일/종료일 없으면 Withdrawal created_at 기준
        if date_from is None:
            first = base_qs.order_by("created_at").values_list("created_at", flat=True).first()
            date_from = first.date() if first else timezone.localdate()
        if date_to is None:
            last = base_qs.order_by("-created_at").values_list("created_at", flat=True).first()
            date_to = last.date() if last else timezone.localdate()

        qs = base_qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)

        # 사유별 집계 (NULL → OTHER로 치환)
        rows = qs.values("reason").annotate(count=Count("id"))
        counts_map: Dict[str, int] = {}
        for r in rows:
            code = r["reason"] or Reason.OTHER.value
            counts_map[code] = r["count"]

        all_codes: List[str] = [m.value for m in Reason]

        value_to_label: Dict[str, str] = dict(Reason.choices)

        total = sum(counts_map.get(code, 0) for code in all_codes)

        items: List[ReasonItem] = []
        for code in all_codes:
            c = counts_map.get(code, 0)
            pct = round((c / total * 100.0), 1) if total else 0.0
            items.append(
                ReasonItem(
                    reason_code=code,
                    reason_label=value_to_label.get(code, Reason.OTHER.label),
                    count=c,
                    percentage=pct,
                )
            )

        # 기본 정렬: count 내림차순 → 동일 시 code 오름차순
        items.sort(key=lambda x: (-x.count, x.reason_code))

        return TrendResult(
            interval="all_time",
            from_date=date_from.strftime("%Y-%m-%d"),
            to_date=date_to.strftime("%Y-%m-%d"),
            total_withdrawals=total,
            items=items,
        )
