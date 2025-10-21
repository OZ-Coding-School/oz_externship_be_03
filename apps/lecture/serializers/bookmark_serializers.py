from rest_framework import serializers

from apps.lecture.models import LectureBookmark
from apps.lecture.serializers.lecture_serializers import LectureListSerializer


class LectureBookmarkListSerializer(serializers.ModelSerializer[LectureBookmark]):
    """북마크한 강의 목록 조회 Serializer."""

    lecture_info = LectureListSerializer(source="lecture", read_only=True)

    class Meta:
        model = LectureBookmark
        fields = [
            "lecture_info",
        ]
