from typing import Any

from rest_framework import serializers


class RecruitmentTagMockSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    recruitment = serializers.IntegerField()
    tag = serializers.CharField()
