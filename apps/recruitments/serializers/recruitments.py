from __future__ import annotations

from typing import Optional

from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.lecture.models import CrawledLecture
from apps.recruitments.models import (
    Bookmark,
    Recruitment,
    RecruitmentAttachment,
    RecruitmentImage,
    Tag,
)
from apps.studies.models import StudyGroup
from apps.users.models import User

# Tag


class TagSerializer(ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name"]


# Image / Attachment


class RecruitmentImageSerializer(ModelSerializer[RecruitmentImage]):
    class Meta:
        model = RecruitmentImage
        fields = ["id", "img_url"]


class RecruitmentAttachmentSerializer(ModelSerializer[RecruitmentAttachment]):
    class Meta:
        model = RecruitmentAttachment
        fields = ["id", "file_name", "file_url"]


# Author
class AuthorSerializer(ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "nickname", "profile_img_url"]


class MyRecruitmentLectureSerializer(serializers.ModelSerializer[CrawledLecture]):
    class Meta:
        model = CrawledLecture
        fields = ["uuid", "title", "instructor", "thumbnail_img_url", "platform", "url_link"]
        read_only_fields = fields


# List
class RecruitmentListSerializer(ModelSerializer[Recruitment]):
    tags = TagSerializer(many=True, read_only=True)
    lectures = MyRecruitmentLectureSerializer(source="study_group.lectures", many=True, read_only=True)
    study_group_name = serializers.CharField(source="study_group.name", read_only=True)
    bookmark_count = serializers.IntegerField(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    thumbnail_img_url = serializers.SerializerMethodField()

    class Meta:
        model = Recruitment
        fields = [
            "uuid",
            "title",
            "thumbnail_img_url",
            "expected_headcount",
            "lectures",
            "study_group_name",
            "tags",
            "close_at",
            "views_count",
            "bookmark_count",
            "is_closed",
            "is_bookmarked",
        ]

    def get_is_bookmarked(self, obj: Recruitment) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return Bookmark.objects.filter(user=request.user, recruitment=obj).exists()

    def get_thumbnail_img_url(self, obj: Recruitment) -> str:
        first_image: Optional[RecruitmentImage] = obj.images.first()
        if first_image:
            return first_image.img_url
        return "https://cdn.default.com/recruitments/default-thumbnail.png"


# Detail


class RecruitmentDetailSerializer(ModelSerializer[Recruitment]):
    """REQ-RECM-006 — 스터디 구인 공고 상세조회"""

    author_nickname = serializers.CharField(source="author.nickname", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    attachments = RecruitmentAttachmentSerializer(many=True, read_only=True)
    lectures = MyRecruitmentLectureSerializer(source="study_group.lectures", many=True, read_only=True)

    bookmark_count = serializers.IntegerField(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    study_group_name = serializers.CharField(source="study_group.name", read_only=True)

    class Meta:
        model = Recruitment
        fields = [
            "uuid",
            "title",
            "content",
            "estimated_fee",
            "expected_headcount",
            "close_at",
            "created_at",
            "views_count",
            "bookmark_count",
            "is_closed",
            "is_bookmarked",
            "study_group_name",
            "lectures",
            "tags",
            "attachments",
            "author_nickname",
        ]

    def get_is_bookmarked(self, obj: Recruitment) -> bool:
        """현재 로그인한 사용자가 북마크했는지 여부"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return Bookmark.objects.filter(user=request.user, recruitment=obj).exists()


# Create / Update


class RecruitmentCreateUpdateSerializer(ModelSerializer[Recruitment]):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=20, allow_blank=True),
        required=False,
        allow_empty=True,
    )
    study_group = serializers.SlugRelatedField(
        slug_field="uuid", queryset=StudyGroup.objects.all(), required=False, allow_null=True
    )
    attachments = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Recruitment
        fields = [
            "title",
            "content",
            "estimated_fee",
            "expected_headcount",
            "close_at",
            "study_group",
            "tags",
            "attachments",
        ]
        extra_kwargs = {
            "estimated_fee": {"required": False, "default": 0},
        }

    def validate_expected_headcount(self, value: int) -> int:
        if value < 1 or value > 10:
            raise serializers.ValidationError("예상 모집 인원은 1~10 사이여야 합니다.")
        return value


# Create Response Serializer


class RecruitmentCreateSerializer(ModelSerializer[Recruitment]):
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Recruitment
        fields = [
            "id",
            "uuid",
            "title",
            "content",
            "estimated_fee",
            "expected_headcount",
            "close_at",
            "study_group",
            "author",
            "tags",
        ]
        read_only_fields = ["id", "uuid", "author"]
