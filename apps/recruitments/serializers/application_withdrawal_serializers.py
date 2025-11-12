from __future__ import annotations

from rest_framework import serializers

from apps.recruitments.models.application import Application


class ApplicationWithdrawalsSerializer(serializers.ModelSerializer[Application]):
    """
    지원 취소 Serializer
    """

    class Meta:
        model = Application
        fields = ["uuid", "status"]
