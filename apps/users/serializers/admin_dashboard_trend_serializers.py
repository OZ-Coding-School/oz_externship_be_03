from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers


class TrendItemSerializer(serializers.Serializer[Dict[str, Any]]):
    period = serializers.CharField()
    count = serializers.IntegerField()


class WithdrawalTrendsDataSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    탈퇴 추세 조회 응답 Serializer
    """

    interval = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    total_withdrawals = serializers.IntegerField()
    items = TrendItemSerializer(many=True)


class SignupTrendsDataSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    가입 추세 조회 응답 Serializer
    """

    interval = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    total_signups = serializers.IntegerField()
    items = TrendItemSerializer(many=True)
