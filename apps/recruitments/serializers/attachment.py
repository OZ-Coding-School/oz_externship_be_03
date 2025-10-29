from rest_framework import serializers

from apps.recruitments.models.attachment import RecruitmentAttachment


class AttachmentSerializer(serializers.ModelSerializer[RecruitmentAttachment]):
    recruitment_id = serializers.IntegerField(source="recruitment_id", read_only=True)

    class Meta:
        model = RecruitmentAttachment
        fields = ("id", "recruitment_id", "file_url", "file_name", "created_at", "updated_at")
        read_only_fields = ("id", "recruitment_id", "created_at", "updated_at")
