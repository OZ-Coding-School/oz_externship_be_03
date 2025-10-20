from rest_framework import serializers

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.serializers.lecture_serializers import LectureListSerializer


class LectureBookmarkButtonSerializer(serializers.ModelSerializer[LectureBookmark]):
    """북마크 추가/삭제 요청 처리용 Serializer."""

    pass


class LectureBookmarkListSerializer(serializers.ModelSerializer[LectureBookmark]):
    """북마크한 강의 목록 조회 Serializer."""

    # source="lecture" 덕분에 LectureBookmark 객체의 lecture 필드를 역참조
    lecture_info = LectureListSerializer(source="lecture", read_only=True)
    duration = serializers.SerializerMethodField(help_text="강의 시간 (HH:MM)")

    class Meta:
        model = LectureBookmark
        fields = [
            "lecture_info",
            "duration",
        ]

    def get_duration(self, obj: LectureBookmark) -> str:
        """분 단위인 duration을 'HH:MM' 형태로 포맷팅."""
        # obj.lecture는 CrawledLecture 객체.
        lecture: CrawledLecture = obj.lecture
        total_min = lecture.duration

        # duration이 null일 경우를 대비하여 방어 코드 추가
        if total_min is None:
            return "00:00"

        hours = total_min // 60
        minutes = total_min % 60
        return f"{hours:02}:{minutes:02}"
