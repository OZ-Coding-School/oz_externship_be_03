from typing import Any, Dict

from rest_framework import serializers


class UserWithdrawalSerializer(serializers.Serializer[Dict[str, Any]]):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    role = serializers.CharField()
    birthday = serializers.DateField()
    reason = serializers.CharField()
    created_at = serializers.DateTimeField()


class PaginationSerializer(serializers.Serializer[Dict[str, Any]]):
    page = serializers.IntegerField()
    limit = serializers.IntegerField()
    total_items = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class WithdrawalListResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    detail = serializers.CharField(read_only=True)

    # ✅ DictField 제거 → mypy에서 Serializer 기본 반환 타입(ReturnDict)과 충돌 방지
    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        users = UserWithdrawalSerializer(instance.get("users", []), many=True).data
        pagination = PaginationSerializer(instance.get("pagination", {})).data
        return {
            "detail": "회원 탈퇴 내역 목록 조회에 성공하였습니다.",
            "data": {
                "users": users,
                "pagination": pagination,
            },
        }
