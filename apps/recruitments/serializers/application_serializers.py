from __future__ import annotations

from typing import Any, Dict, Optional

from rest_framework import serializers

from apps.recruitments.models.application import Application


class ApplicationCreateSerializer(serializers.ModelSerializer[Any]):
    """
    스터디 공고 지원 요청 Serializer
    """

    class Meta:
        model = Application
        fields = (
            "self_introduction",
            "motivation",
            "objective",
            "available_time",
            "has_study_experience",
            "study_experience",
        )

    # study_experience는 선택 입력(allow_blank=True, required=False)
    study_experience = serializers.CharField(allow_blank=True, required=False)


class ApplicationResponseSerializer(serializers.Serializer[Any]):
    """
    스터디 공고 지원 응답 Serializer
    """

    uuid = serializers.UUIDField()
    recruitment_uuid = serializers.UUIDField(source="recruitment.uuid")
    recruitment_title = serializers.CharField(source="recruitment.title")
    user_uuid = serializers.SerializerMethodField()

    self_introduction = serializers.CharField()
    motivation = serializers.CharField()
    objective = serializers.CharField()
    available_time = serializers.CharField()
    has_study_experience = serializers.BooleanField()
    study_experience = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()

    def get_user_uuid(self, obj: Application) -> Optional[str]:
        u = getattr(obj.user, "uuid", None)
        return str(u) if u else None
