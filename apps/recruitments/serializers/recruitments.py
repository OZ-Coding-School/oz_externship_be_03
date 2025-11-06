from rest_framework import serializers

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.tag import TagSerializer


class RecruitmentSerializer(serializers.ModelSerializer[Recruitment]):

    class Meta:
        model = Recruitment
        fields = "__all__"
        extra_kwargs = {
            "uuid": {"read_only": True},
            "created_at": {"read_only": True},
            "updated_at": {"read_only": True},
            "views_count": {"default": 0},
            "is_closed": {"default": False},
            "study_group": {"required": False, "allow_null": True},
            "author": {"required": False},
        }


class RecruitmentDetailSerializer(RecruitmentSerializer):
    """공고 상세 조회 시 태그 정보를 함께 직렬화"""

    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Recruitment
        fields = RecruitmentSerializer.Meta.fields + ["tags"]
