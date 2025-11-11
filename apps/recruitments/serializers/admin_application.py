from typing import Any
from rest_framework import serializers
from apps.recruitments.models import Application

# 모집 공고 요약 정보를 담는 시리얼라이저 (관리자 상세 조회 응답용)
class RecruitmentSummarySerializer(serializers.Serializer[Application]):
    id = serializers.IntegerField()  # 모집 공고 ID
    title = serializers.CharField()  # 모집 공고 제목
    expected_headcount = serializers.IntegerField()  # 모집 인원
    close_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M")  # 모집 마감일
    tags = serializers.ListField(child=serializers.CharField())  # 태그 목록 (문자열 리스트)

# 지원자 요약 정보를 담는 시리얼라이저 (관리자 상세 조회 응답용)
class ApplicantSummarySerializer(serializers.Serializer[Application]):
    id = serializers.IntegerField()  # 지원자 ID
    nickname = serializers.CharField()  # 닉네임
    email = serializers.EmailField()  # 이메일
    profile_image = serializers.URLField()  # 프로필 이미지 URL

# 관리자용 지원서 목록 조회 시리얼라이저
class AdminApplicationListSerializer(serializers.ModelSerializer[Application]):
    recruitment_title = serializers.CharField(source="recruitment.title")  # 모집 공고 제목
    applicant_nickname = serializers.CharField(source="user.nickname")  # 지원자 닉네임
    applicant_email = serializers.EmailField(source="user.email")  # 지원자 이메일

    class Meta:
        model = Application
        fields = [
            "id",  # 지원서 ID
            "recruitment_title",  # 모집 공고 제목
            "applicant_nickname",  # 지원자 닉네임
            "applicant_email",  # 지원자 이메일
            "status",  # 지원 상태
            "created_at",  # 생성일
            "updated_at",  # 수정일
        ]

# 관리자용 지원서 상세 조회 시리얼라이저
class AdminApplicationDetailSerializer(serializers.ModelSerializer[Application]):
    recruitment = serializers.SerializerMethodField()  # 모집 공고 요약 정보
    applicant = serializers.SerializerMethodField()  # 지원자 요약 정보

    def get_recruitment(self, obj: Application) -> dict[str, Any]:
        # 모집 공고 요약 정보를 dict 형태로 반환
        return {
            "id": obj.recruitment.id,
            "title": obj.recruitment.title,
            "expected_headcount": obj.recruitment.expected_headcount,
            "close_at": obj.recruitment.close_at,
            "tags": [tag.name for tag in obj.recruitment.tags.all()],
        }

    def get_applicant(self, obj: Application) -> dict[str, Any]:
        # 지원자 요약 정보를 dict 형태로 반환
        return {
            "id": obj.user.id,
            "nickname": obj.user.nickname,
            "email": obj.user.email,
            "profile_image": obj.user.profile_img_url,
        }

    class Meta:
        model = Application
        fields = [
            "id",  # 지원서 ID
            "status",  # 지원 상태
            "created_at",  # 생성일
            "updated_at",  # 수정일
            "self_introduction",  # 자기소개
            "motivation",  # 지원 동기
            "objective",  # 목표
            "available_time",  # 가능 시간
            "has_study_experience",  # 스터디 경험 여부
            "study_experience",  # 스터디 경험 설명
            "recruitment",  # 모집 공고 요약 정보
            "applicant",  # 지원자 요약 정보
        ]