from __future__ import annotations

from typing import Any, List

from rest_framework import serializers

from apps.recruitments.models import Tag


class TagSearchResultSerializer(serializers.ModelSerializer[Any]):
    """태그 검색 결과를 위한 Serializer"""

    class Meta:
        model = Tag
        fields = ["id", "name"]


class RecruitmentTagAddSerializer(serializers.Serializer[Any]):
    """스터디 구인 공고 작성/수정 시 태그 등록 요청용 Serializer"""

    tags = serializers.ListField(
        child=serializers.CharField(max_length=20),
        allow_empty=False,
    )

    def validate_tags(self, value: List[str]) -> List[str]:
        """공고당 태그는 최대 5개까지 제한"""
        if len(value) > 5:
            raise serializers.ValidationError("공고당 태그는 최대 5개까지 추가할 수 있습니다.")
        return value
