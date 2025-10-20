from typing import Any, cast

from rest_framework import serializers
from rest_framework.utils.serializer_helpers import ReturnDict

from apps.lecture.models import Category, CrawledLecture


class CategorySerializer(serializers.ModelSerializer[Category]):
    """카테고리 Serializer"""

    class Meta:
        model = Category
        fields = ["id", "name"]


class LectureListSerializer(serializers.ModelSerializer[CrawledLecture]):
    """강의 목록 조회용 Serializer (일반사용자)"""

    categories = serializers.SerializerMethodField()

    class Meta:
        model = CrawledLecture
        fields = [
            "id",
            "uuid",
            "title",
            "instructor",
            "thumbnail_img_url",
            "categories",
            "difficulty",
            "original_price",
            "discount_price",
            "platform",
            "average_rating",
            "url_link",
        ]

    def get_categories(self, obj: CrawledLecture) -> ReturnDict[Any, Any]:
        """강의에 속한 카테고리 목록 반환"""
        lecture_categories = obj.lecture_categories.all()

        categories = []
        for lecture_category in lecture_categories:
            category = lecture_category.category
            categories.append(category)

        serializer = CategorySerializer(categories, many=True)
        return serializer.data
