from rest_framework import serializers

from apps.recruitments.models.recruitment_tag import RecruitmentTag


class RecruitmentTagSerializer(serializers.ModelSerializer[RecruitmentTag]):
    recruitment: serializers.StringRelatedField = serializers.StringRelatedField()  # type: ignore
    tag: serializers.StringRelatedField = serializers.StringRelatedField()  # type: ignore

    class Meta:
        model = RecruitmentTag
        fields = ["id", "recruitment", "tag", "created_at", "updated_at"]
