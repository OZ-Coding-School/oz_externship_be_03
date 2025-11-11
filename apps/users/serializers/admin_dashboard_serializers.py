from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.users.services.admin_dashboard_services import (
    ReasonItem,
    TrendItem,
    TrendResult,
)


class WithdrawalPeriodItemSerializer(serializers.Serializer[dict[str, Any]]):
    """
    기간별(월/연) 탈퇴 건수 아이템 Serializer
    """

    period = serializers.CharField()
    count = serializers.IntegerField()


class WithdrawalReasonItemSerializer(serializers.Serializer[dict[str, Any]]):
    """
    단일 탈퇴 사유 통계 아이템 Serializer
    """

    reason_code = serializers.CharField()
    reason_label = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.FloatField()


class AdminWithdrawalReasonTrendResponseSerializer(serializers.Serializer[TrendResult[TrendItem]]):
    """
    탈퇴 사유 추적(월/연 트렌드) 조회 응답 Serializer
    """

    interval = serializers.ChoiceField(choices=["month", "year"])
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    total_withdrawals = serializers.IntegerField()
    items = WithdrawalPeriodItemSerializer(many=True)


class AdminWithdrawalReasonDistributionResponseSerializer(serializers.Serializer[TrendResult[ReasonItem]]):
    """
    탈퇴 사유 분포(전체 기간) 조회 응답 Serializer
    """

    interval = serializers.ChoiceField(choices=["all_time"])
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    total_withdrawals = serializers.IntegerField()
    items = WithdrawalReasonItemSerializer(many=True)
