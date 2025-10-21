from typing import Any, Dict

from django.db import IntegrityError, transaction
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

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        user = self.context["request"].user
        lecture = attrs.get("lecture")
        # 사전 중복 체크로 명확한 오류 메시지 제공
        if LectureBookmark.objects.filter(user=user, lecture=lecture).exists():
            raise ValidationError({"detail": "이미 북마크한 강의입니다."})
        return attrs

    @transaction.atomic
    def create(self, validated_data: Dict[str, Any]) -> LectureBookmark:
        user = self.context["request"].user
        lecture = validated_data["lecture"]

        try:
            bookmark = LectureBookmark.objects.create(user=user, lecture=lecture)
        except IntegrityError:
            raise ValidationError({"detail": "이미 북마크한 강의입니다."})
        return bookmark
