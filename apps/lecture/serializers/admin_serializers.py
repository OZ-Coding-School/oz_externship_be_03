from rest_framework import serializers

from apps.lecture.models import CrawledLecture
from apps.lecture.serializers.category_serializers import CategoryListSerializer


class AdminLectureListSerializer(serializers.ModelSerializer[CrawledLecture]):
    """강의 목록 조회용 Serializer (관리자)"""

    categories = CategoryListSerializer(many=True, read_only=True)

    class Meta:
        model = CrawledLecture
        fields = [
            "id",
            "title",
            "instructor",
            "thumbnail_img_url",
            "platform",
            "url_link",
            "categories",
            "created_at",
            "updated_at",
        ]


class AdminLectureDetailSerializer(serializers.ModelSerializer[CrawledLecture]):
    """강의 상세 조회용 Serializer (관리자)"""

    categories = CategoryListSerializer(many=True, read_only=True)

    class Meta:
        model = CrawledLecture
        fields = [
            "id",
            "uuid",
            "title",
            "instructor",
            "thumbnail_img_url",
            "description",
            "difficulty",
            "duration",
            "original_price",
            "discount_price",
            "platform",
            "url_link",
            "categories",
            "created_at",
            "updated_at",
        ]
