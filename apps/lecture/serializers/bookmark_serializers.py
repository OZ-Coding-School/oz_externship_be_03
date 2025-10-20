from typing import Any, Dict, List

from rest_framework import serializers

from apps.lecture.models import LectureBookmark


class LectureBookmarkSerializer(serializers.ModelSerializer[LectureBookmark]):
    """LectureBookmark 모델과 연동된 북마크 용 강의 정보 직렬화하는 Serializer"""

    # 강의 필드들을 lecture 외래키를 통해 참조하여 읽기 전용으로 노출
    id = serializers.IntegerField(source="lecture.id", read_only=True)
    uuid = serializers.UUIDField(source="lecture.uuid", read_only=True)
    title = serializers.CharField(source="lecture.title", read_only=True)
    instructor = serializers.CharField(source="lecture.instructor", read_only=True)
    thumbnail_img_url = serializers.CharField(source="lecture.thumbnail_img_url", read_only=True)
    difficulty = serializers.CharField(source="lecture.difficulty", read_only=True)
    original_price = serializers.IntegerField(source="lecture.original_price", read_only=True)
    discount_price = serializers.IntegerField(source="lecture.discount_price", read_only=True)
    platform = serializers.CharField(source="lecture.platform", read_only=True)
    average_rating = serializers.DecimalField(
        source="lecture.average_rating", max_digits=3, decimal_places=2, read_only=True
    )
    duration = serializers.SerializerMethodField()
    url_link = serializers.URLField(source="lecture.url_link", read_only=True)
    description = serializers.CharField(source="lecture.description", read_only=True)
    categories = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    bookmarked_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = LectureBookmark
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
            "reviews",
            "bookmarked_at",
        ]

    def get_categories(self, obj: LectureBookmark) -> list[str]:
        """카테고리 이름 목록 조회"""
        return [lc.category.name for lc in obj.lecture.lecture_categories.all()]

    def get_reviews(self, obj: LectureBookmark) -> List[Dict[str, Any]]:
        """최신 4건 리뷰 평점과 내용 반환"""
        reviews = obj.lecture.reviews.all().order_by("-created_at")[:4]
        return [{"rating": review.rating, "content": review.content} for review in reviews]

    def get_duration(self, obj: LectureBookmark) -> str:
        total_min = obj.lecture.duration
        hours, minutes = divmod(total_min, 60)
        return f"{hours:02}:{minutes:02}"


class LectureBookmarkButtonSerializer(serializers.ModelSerializer[LectureBookmark]):
    """북마크 추가/삭제 요청용 Serializer"""

    class Meta:
        model = LectureBookmark
        fields = ["user", "lecture"]

    def validate_lecture(self, value: Any) -> Any:
        """유효성 검사: 전달된 lecture가 실제 존재하는지 확인"""
        if not value.pk or (not value._state.adding and not value.__class__.objects.filter(pk=value.pk).exists()):
            raise serializers.ValidationError("존재하지 않는 강의입니다.")
        return value
