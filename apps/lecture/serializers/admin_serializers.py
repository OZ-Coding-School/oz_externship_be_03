from typing import Any

from rest_framework import serializers
from rest_framework.utils.serializer_helpers import ReturnDict

from apps.lecture.models import CrawledLecture
from apps.lecture.serializers.lecture_serializers import LectureListSerializer


class AdminLectureListSerializer(serializers.ModelSerializer[CrawledLecture]):
    """강의 목록 조회용 Serializer (관리자)"""

    categories = serializers.SerializerMethodField()

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

    def get_categories(self, obj: CrawledLecture) -> ReturnDict[Any, Any]:
        return LectureListSerializer().get_categories(obj)


class AdminLectureDetailSerializer(serializers.ModelSerializer[CrawledLecture]):
    """강의 상세 조회용 Serializer (관리자)"""

    categories = serializers.SerializerMethodField()

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

    def get_categories(self, obj: CrawledLecture) -> ReturnDict[Any, Any]:
        return LectureListSerializer().get_categories(obj)
