from __future__ import annotations

from typing import Optional

from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.recruitments.models import (
    Bookmark,
    Recruitment,
    RecruitmentAttachment,
    RecruitmentImage,
    Tag,
)
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


# List


class RecruitmentListSerializer(ModelSerializer[Recruitment]):
    tags = TagSerializer(many=True, read_only=True)
    bookmark_count = serializers.IntegerField(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    thumbnail_img = serializers.SerializerMethodField()
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Recruitment
        fields = [
            "id",
            "uuid",
            "title",
            "thumbnail_img",
            "expected_headcount",
            "author",
            "tags",
            "close_at",
            "views_count",
            "bookmark_count",
            "is_bookmarked",
        ]

    def get_is_bookmarked(self, obj: Recruitment) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return Bookmark.objects.filter(user=request.user, recruitment=obj).exists()

    def get_thumbnail_img(self, obj: Recruitment) -> str:
        first_image: Optional[RecruitmentImage] = obj.images.first()
        if first_image:
            return first_image.img_url
        return "https://cdn.default.com/recruitments/default-thumbnail.png"


# Detail


class RecruitmentDetailSerializer(ModelSerializer[Recruitment]):
    tags = TagSerializer(many=True, read_only=True)
    images = RecruitmentImageSerializer(many=True, read_only=True)
    attachments = RecruitmentAttachmentSerializer(many=True, read_only=True)
    bookmark_count = serializers.IntegerField(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    author = serializers.CharField(source="author.nickname", read_only=True)

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
            "tags",
            "images",
            "attachments",
            "views_count",
            "bookmark_count",
            "author",
            "created_at",
            "is_bookmarked",
        ]

    def get_is_bookmarked(self, obj: Recruitment) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return Bookmark.objects.filter(user=request.user, recruitment=obj).exists()


# Create / Update


class RecruitmentCreateUpdateSerializer(ModelSerializer[Recruitment]):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        allow_empty=True,
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
        ]

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
