from rest_framework import serializers

from apps.recruitments.models.recruitment_images import RecruitmentImage


class ImagesSerializer(serializers.ModelSerializer[RecruitmentImage]):
    recruitment_id = serializers.IntegerField(source="recruitment_id", read_only=True)

    class Meta:
        model = RecruitmentImage
        fields = ("id", "recruitment_id", "img_url", "created_at", "updated_at")
        read_only_fields = ("id", "recruitment_id", "created_at", "updated_at")
