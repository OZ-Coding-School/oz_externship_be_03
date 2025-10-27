from rest_framework import serializers

from apps.recruitments.models import RecruitmentAttachment


class AttachmentSerializer(serializers.ModelSerializer[RecruitmentAttachment]):
    id = serializers.IntegerField(read_only=True)
    recruitment_id = serializers.IntegerField(read_only=True)
    file_url = serializers.CharField(max_length=255)
    file_name = serializers.CharField(max_length=50)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

class Meta:
        model = RecruitmentAttachment
        fields = '__all__'