from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers


class WithdrawalListItemSerializer(serializers.Serializer[Dict[str, Any]]):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    role = serializers.CharField()
    birthday = serializers.DateField(allow_null=True)
    reason = serializers.CharField()
    withdrawn_at = serializers.DateTimeField()


class WithdrawalListResponseSerializer(serializers.Serializer[Dict[str, Any]]):
    users = serializers.ListField(child=WithdrawalListItemSerializer())
    pagination = serializers.DictField()
