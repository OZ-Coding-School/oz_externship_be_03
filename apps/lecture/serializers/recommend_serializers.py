from typing import Any, Dict, List

from rest_framework import serializers

from apps.lecture.models import CrawledLecture


class RecommendedLectureSerializer(serializers.ModelSerializer[CrawledLecture]):
    """추천 단일 강의 직렬화 ModelSerializer"""

    categories = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

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
            "duration",
            "url_link",
            "description",
        ]

    def get_categories(self, obj: CrawledLecture) -> List[Dict[str, Any]]:
        return [{"id": lc.category.id, "name": lc.category.name} for lc in obj.lecture_categories.all()]

    def get_duration(self, obj: CrawledLecture) -> str:
        total_min = obj.duration
        hours, minutes = divmod(total_min, 60)
        return f"{hours:02}:{minutes:02}"


class RecommendedLecturesDTO(serializers.Serializer[Dict[str, Any]]):
    """사용자 닉네임과 추천 강의 리스트 DTO용 Serializer"""

    nickname = serializers.CharField()
    recommendations = RecommendedLectureSerializer(many=True)
