from typing import Any, Dict

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.serializers.lecture_serializers import LectureListSerializer


class LectureBookmarkListSerializer(serializers.ModelSerializer[LectureBookmark]):
    """북마크한 강의 목록 조회 Serializer."""

    lecture_info = LectureListSerializer(source="lecture", read_only=True)

    class Meta:
        model = LectureBookmark
        fields = [
            "id",
            "lecture_info",
            "created_at",
        ]


class LectureBookmarkCreateSerializer(serializers.ModelSerializer[LectureBookmark]):
    """북마크 추가 Serializer."""

    lecture_id = serializers.PrimaryKeyRelatedField(
        queryset=CrawledLecture.objects.all(),
        source="lecture",
        write_only=True,
        help_text="북마크할 강의의 ID",
    )

    class Meta:
        model = LectureBookmark
        fields = ["lecture_id"]

    def create(self, validated_data: Dict[str, Any]) -> LectureBookmark:
        # 1. DRF 표준: 뷰에서 serializer.save(user=request.user)로 전달된
        # 'user' 객체를 validated_data에서 안전하게 추출.
        user = validated_data.pop("user")
        lecture = validated_data.pop("lecture")

        # 2. get_or_create를 사용하여 중복 체크, 생성을 단일 쿼리(원자적)로 처리.
        bookmark, created = LectureBookmark.objects.get_or_create(user=user, lecture=lecture)

        if not created:
            # 이미 존재할 경우 명확한 ValidationError 반환.
            raise ValidationError({"detail": "이미 북마크한 강의입니다."})

        return bookmark
