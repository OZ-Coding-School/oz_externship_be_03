from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Literal, Type, TypedDict, cast

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone

from apps.users.models import Withdrawal

User = cast(type[models.Model], get_user_model())

Interval = Literal["month", "year"]


class TrendItem(TypedDict):
    period: str
    count: int


class TrendResult(TypedDict):
    interval: Interval
    from_date: date
    to_date: date
    total: int
    items: List[TrendItem]


def _month_window(today: date, months: int = 12) -> Dict[str, date]:
    """최근 12개월 (이번 달 포함) 기간 계산"""
    year, month = today.year, today.month
    offset_total = (year * 12 + month) - (months - 1)
    start_year = (offset_total - 1) // 12
    start_month = offset_total - start_year * 12
    start = date(start_year, start_month, 1)

    return {"start": start, "end": today}


def _year_window(today: date, years: int = 5) -> Dict[str, date]:
    """최근 5년 (올해 포함) 기간 계산"""
    start = date(today.year - years + 1, 1, 1)
    return {"start": start, "end": today}


def _to_aware(dt: datetime) -> datetime:
    """naive -> 현재 타임존 aware, 이미 aware면 그대로"""
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt, timezone.get_current_timezone())


def _aggregate(*, model: Type[models.Model], filters: Q | Dict[str, Any] | None, interval: Interval) -> TrendResult:
    """
    공통 추세
    주어진 모델과 날짜 필드를 기준으로 월/연 단위로 집계.
    빠진 구간은 count=0으로 채워 반환
    """
    today = timezone.localdate()
    window = _month_window(today) if interval == "month" else _year_window(today)

    start_datetime = _to_aware(datetime.combine(window["start"], datetime.min.time()))
    end_datetime = _to_aware(datetime.combine(window["end"] + timedelta(days=1), datetime.min.time()))

    queryset = cast(Any, model).objects.filter(
        created_at__gte=start_datetime,
        created_at__lt=end_datetime,
    )
    if filters:
        queryset = queryset.filter(filters)

    trend_items: List[TrendItem] = []

    if interval == "month":
        # 1) 월별 집계 쿼리 실행
        aggregated = queryset.annotate(bucket=TruncMonth("created_at")).values("bucket").annotate(count=Count("id"))

        # 2) { (year, month): count } 형태의 매핑 생성
        month_trend_map: Dict[tuple[int, int], int] = {
            (record["bucket"].year, record["bucket"].month): int(record["count"])
            for record in aggregated
            if record["bucket"]  # bucket이 None인 경우 방어
        }

        # 3) 시작월 ~ 종료월 순회하면서 누락 구간은 count=0으로 채움
        year, month = window["start"].year, window["start"].month
        while True:
            count = month_trend_map.get((year, month), 0)
            trend_items.append({"period": f"{year:04d}-{month:02d}", "count": count})

            # 종료 조건
            if year == window["end"].year and month == window["end"].month:
                break

            # 다음 달로 이동
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

    else:  # interval == "year"
        # 1) 연도별 집계 쿼리 실행
        aggregated = queryset.annotate(bucket=TruncYear("created_at")).values("bucket").annotate(count=Count("id"))

        # 2) { year: count } 형태의 매핑 생성
        year_trend_map: Dict[int, int] = {
            record["bucket"].year: int(record["count"]) for record in aggregated if record["bucket"]
        }

        # 3) 시작연도 ~ 종료연도 순회하면서 누락 구간은 count=0으로 채움
        for year in range(window["start"].year, window["end"].year + 1):
            count = year_trend_map.get(year, 0)
            trend_items.append({"period": f"{year:04d}", "count": count})

    # 총합 계산
    total_count = queryset.aggregate(total=Count("id"))["total"] or 0

    return {
        "interval": interval,
        "from_date": window["start"],
        "to_date": window["end"],
        "total": total_count,
        "items": trend_items,
    }


def get_withdrawal_trends(*, interval: Interval) -> TrendResult:
    """탈퇴 추세 조회 (월/년 단위)"""
    filters = Q(user_id__isnull=True)

    return _aggregate(
        model=Withdrawal,
        filters=filters,
        interval=interval,
    )


def get_signup_trends(*, interval: Interval) -> TrendResult:
    """가입 추세 조회 (월/년 단위)"""

    return _aggregate(
        model=User,
        filters=None,
        interval=interval,
    )
