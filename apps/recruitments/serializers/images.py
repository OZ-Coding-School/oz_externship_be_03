from rest_framework import serializers


from apps.recruitments.models.images import RecruitmentImages


class ImagesSerializer(serializers.ModelSerializer[RecruitmentImages]):
    id = serializers.IntegerField(read_only=True)
    recruitment_id = serializers.IntegerField(read_only=True)
    img_url = serializers.URLField(max_length=255)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = RecruitmentImages
        fields = '__all__'