from rest_framework import serializers

from apps.recruitments.models.recruitments import Recruitment


class RecruitmentSerializer(serializers.ModelSerializer[Recruitment]):

    class Meta:
        model = Recruitment
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True},
            "uuid": {"read_only": True},
            "created_at": {"read_only": True},
            "updated_at": {"read_only": True},
            "views_count": {"default": 0},
            "is_closed": {"default": False},
            "study_group": {"required": False, "allow_null": True},
            "author": {"required": False},
        }


class RecruitmentDetailSerializer(RecruitmentSerializer):
    pass
