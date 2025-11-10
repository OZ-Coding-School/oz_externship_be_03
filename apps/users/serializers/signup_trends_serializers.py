from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict

from rest_framework import serializers


# TODO : 회원 탈퇴 추세 API에 있는 것 사용
class TrendItemSerializer(serializers.Serializer[Dict[str, Any]]):
    period = serializers.CharField()
    count = serializers.IntegerField()


class SignupTrendsDataSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    가입 추세 조회 응답 Serializer
    """

    interval = serializers.CharField()
    from_ = serializers.DateField(source="from")
    to = serializers.DateField()
    total_signups = serializers.IntegerField()
    items = TrendItemSerializer(many=True)

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        rep = super().to_representation(instance)
        # 출력 키를 'from'으로 교체
        rep["from"] = rep.pop("from_")

        # 원하는 순서로 재정렬
        ordered = OrderedDict()
        for key in ["interval", "from", "to", "total_signups", "items"]:
            if key in rep:
                ordered[key] = rep[key]
        return ordered
