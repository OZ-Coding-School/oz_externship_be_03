from rest_framework import serializers

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.tag import TagSerializer


class AdminRecruitmentSerializer(serializers.ModelSerializer[Recruitment]):
    """관리자용 구인 공고 목록/상세 Serializer"""

    tags = TagSerializer(many=True, read_only=True)
    author_nickname = serializers.CharField(source="author.nickname", read_only=True)
    study_group_name = serializers.CharField(source="study_group.name", read_only=True, allow_null=True)

    class Meta:
        model = Recruitment
        fields = [
            "id",
            "uuid",
            "title",
            "content",
            "estimated_fee",
            "expected_headcount",
            "views_count",
            "close_at",
            "is_closed",
            "created_at",
            "updated_at",
            "author_nickname",
            "study_group_name",
            "tags",
        ]


class AdminRecruitmentDetailSerializer(AdminRecruitmentSerializer):
    """관리자용 구인 공고 상세 Serializer"""

    class Meta(AdminRecruitmentSerializer.Meta):
        pass
