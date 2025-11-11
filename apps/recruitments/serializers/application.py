from typing import Any
from rest_framework import serializers
from apps.recruitments.models import Application


# 사용자용 지원서 시리얼라이저

class ApplicationCreateSerializer(serializers.ModelSerializer[Application]):
    # 지원서 작성 요청 시 사용되는 시리얼라이저
    class Meta:
        model = Application
        fields = [
            "recruitment", "self_introduction", "motivation", "objective",
            "available_time", "has_study_experience", "study_experience"
        ]
        read_only_fields = ["user"]

    def create(self, validated_data: dict[str, Any]) -> Application:
        # 현재 로그인한 사용자 정보를 user 필드에 자동 삽입
        user = self.context["request"].user
        return Application.objects.create(user=user, **validated_data)


class ApplicationDetailSerializer(serializers.ModelSerializer[Application]):
    # 지원서 전체 필드 응답용 시리얼라이저 (관리자/사용자 공용)
    class Meta:
        model = Application
        fields = "__all__"


class MyApplicationListSerializer(serializers.ModelSerializer[Application]):
    # 사용자용 지원서 목록 조회 시리얼라이저
    recruitment_title = serializers.CharField(source="recruitment.title")

    class Meta:
        model = Application
        fields = ["id", "recruitment_title", "status", "created_at", "updated_at"]


class MyApplicationDetailSerializer(serializers.ModelSerializer[Application]):
    # 사용자용 지원서 상세 조회 시리얼라이저
    recruitment = serializers.SerializerMethodField()

    def get_recruitment(self, obj: Application) -> dict[str, Any]:
        # 모집 공고 요약 정보 반환
        return {
            "id": obj.recruitment.id,
            "title": obj.recruitment.title,
            "expected_headcount": obj.recruitment.expected_headcount,
            "close_at": obj.recruitment.close_at,
        }

    class Meta:
        model = Application
        fields = [
            "id", "status", "created_at", "updated_at",
            "self_introduction", "motivation", "objective",
            "available_time", "has_study_experience", "study_experience",
            "recruitment"
        ]