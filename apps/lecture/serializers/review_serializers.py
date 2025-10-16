from rest_framework import serializers

from apps.lecture.models import CrawledLectureReview


class LectureReviewSerializer(serializers.ModelSerializer[CrawledLectureReview]):
    """강의 리뷰 조회용 Serializer"""

    class Meta:
        model = CrawledLectureReview
        fields = [
            "id",
            "rating",
            "content",
            "created_at",
        ]
