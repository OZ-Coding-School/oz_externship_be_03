from rest_framework import serializers

from apps.recruitments.models import Recruitment, RecruitmentAttachment, Tag
from apps.recruitments.models.application import Application


class AdminRecruitmentTagSerializer(serializers.ModelSerializer[Tag]):
    """관리자용 태그"""

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name"]


class AdminRecruitmentAttachmentSerializer(serializers.ModelSerializer[RecruitmentAttachment]):
    """관리자용 첨부파일"""

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = RecruitmentAttachment
        fields = ["id", "file_name", "file_url"]


class AdminApplicationSerializer(serializers.ModelSerializer[Application]):
    """관리자용 지원내역"""

    id = serializers.IntegerField(read_only=True)  #
    nickname = serializers.CharField(source="user.nickname", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    applied_at = serializers.DateTimeField(source="created_at", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "nickname", "email", "applied_at", "status", "status_display"]


class AdminRecruitmentListSerializer(serializers.ModelSerializer[Recruitment]):
    """관리자용 공고 목록"""

    tags: serializers.SlugRelatedField[Tag] = serializers.SlugRelatedField(slug_field="name", read_only=True, many=True)
    status = serializers.SerializerMethodField()
    bookmark_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Recruitment
        fields = [
            "id",
            "uuid",
            "title",
            "tags",
            "is_closed",
            "close_at",
            "status",
            "views_count",
            "bookmark_count",
            "created_at",
            "updated_at",
        ]

    def get_status(self, obj: Recruitment) -> str:
        """공고 상태 (모집중 / 마감)"""
        return "마감" if obj.is_closed else "모집중"


class AdminRecruitmentDetailSerializer(serializers.ModelSerializer[Recruitment]):
    """관리자용 공고 상세"""

    attachments = AdminRecruitmentAttachmentSerializer(many=True, read_only=True)
    tags = AdminRecruitmentTagSerializer(many=True, read_only=True)
    applications = AdminApplicationSerializer(many=True, read_only=True)
    bookmark_count = serializers.SerializerMethodField()

    class Meta:
        model = Recruitment
        fields = [
            "id",
            "uuid",
            "title",
            "content",
            "attachments",
            "expected_headcount",
            "estimated_fee",
            "tags",
            "close_at",
            "is_closed",
            "created_at",
            "updated_at",
            "views_count",
            "bookmark_count",
            "applications",
        ]

    def get_bookmark_count(self, obj: Recruitment) -> int:
        """SerializerMethodField 명시적 반환"""
        return getattr(obj, "bookmark_count", 0)
