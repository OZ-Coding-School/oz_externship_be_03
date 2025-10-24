from rest_framework import serializers

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.serializers.category_serializers import CategoryListSerializer


class LectureListSerializer(serializers.ModelSerializer[CrawledLecture]):
    """강의 목록 조회용 Serializer (일반사용자)"""

    categories = CategoryListSerializer(many=True, read_only=True)
    is_bookmarked = serializers.SerializerMethodField()

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
            "is_bookmarked",
        ]

    def get_is_bookmarked(self, obj: CrawledLecture) -> bool:
        """현재 사용자의 북마크 여부"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return LectureBookmark.objects.filter(user=request.user, lecture=obj).exists()
        return False
