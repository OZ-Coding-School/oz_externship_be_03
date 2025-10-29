from rest_framework import serializers

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.tag import TagSerializer


class RecruitmentDetailSerializer(serializers.ModelSerializer[Recruitment]):
    """공고 상세 조회 시 태그 정보를 함께 직렬화"""

    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Recruitment
        fields = [
            "id",
            "title",
            "content",
            "estimated_fee",
            "expected_headcount",
            "views_count",
            "close_at",
            "is_closed",
            "tags",
        ]
