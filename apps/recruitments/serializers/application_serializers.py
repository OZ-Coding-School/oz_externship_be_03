from __future__ import annotations

from typing import Any, Optional

from rest_framework import serializers

from apps.recruitments.models.application import Application
from apps.users.models import User


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


class ApplicantSerializer(serializers.ModelSerializer[User]):
    """
    지원자 기본 정보 serializer
    """

    class Meta:
        model = User
        fields = ["nickname", "gender", "profile_img_url"]


class ApplicationListSerializer(serializers.ModelSerializer[Application]):
    """
    지원 내역 목록 조회용 serializer
    """

    applicant = ApplicantSerializer(source="user", read_only=True)
    applied_at = serializers.DateTimeField(source="created_at", format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "uuid",
            "applicant",
            "available_time",
            "has_study_experience",
            "status",
            "applied_at",
        ]


class ApplicationDetailSerializer(serializers.ModelSerializer[Application]):
    """
    지원 내역 상세 조회용 serializer
    """

    applicant = ApplicantSerializer(source="user", read_only=True)
    applied_at = serializers.DateTimeField(source="created_at", format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "uuid",
            "applicant",
            "self_introduction",
            "motivation",
            "objective",
            "available_time",
            "has_study_experience",
            "study_experience",
            "status",
            "applied_at",
        ]
