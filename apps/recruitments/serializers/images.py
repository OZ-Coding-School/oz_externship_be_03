from rest_framework import serializers

from apps.recruitments.models.recruitment_images import RecruitmentImage


class ImagesSerializer(serializers.ModelSerializer[RecruitmentImage]):
    id = serializers.IntegerField(read_only=True)
    recruitment_id = serializers.IntegerField(read_only=True)
    img_url = serializers.URLField(max_length=255)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = RecruitmentImage
        fields = "__all__"
