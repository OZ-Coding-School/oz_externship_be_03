from rest_framework import serializers

from apps.recruitments.models import Application
from apps.users.models import User


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