from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.studies.models.notes import StudyNote

User = get_user_model()


class AuthorSlimSerializer(serializers.ModelSerializer[Any]):
    """작성자 최소 정보 직렬화"""

    class Meta:
        model = User
        fields = ("id", "nickname")  # username → nickname 으로 교정


class StudyNoteCreateSerializer(serializers.ModelSerializer[StudyNote]):
    """노트 생성용 Serializer"""

    class Meta:
        model = StudyNote
        fields = ("title", "content")

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """필수 항목 검증"""
        if not attrs.get("title"):
            raise serializers.ValidationError({"title": "필수 항목입니다."})
        if not attrs.get("content"):
            raise serializers.ValidationError({"content": "필수 항목입니다."})
        return attrs


class StudyNoteUpdateSerializer(serializers.ModelSerializer[StudyNote]):
    """노트 수정용 Serializer"""

    class Meta:
        model = StudyNote
        fields = ("title", "content")
        extra_kwargs = {"title": {"required": False}, "content": {"required": False}}

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError({"error": "title 또는 content 중 하나는 필요합니다."})
        return attrs


class StudyNoteListItemSerializer(serializers.ModelSerializer[StudyNote]):
    """노트 목록 Serializer"""

    author = AuthorSlimSerializer(read_only=True)
    group_id = serializers.IntegerField(source="study_group_id", read_only=True)

    class Meta:
        model = StudyNote
        # group_id 필드 포함
        fields = ("id", "group_id", "title", "ai_summary", "author", "created_at")
        read_only_fields = fields


class StudyNoteDetailSerializer(serializers.ModelSerializer[StudyNote]):
    """노트 단일 조회 Serializer"""

    author = AuthorSlimSerializer(read_only=True)
    group_id = serializers.IntegerField(source="study_group_id", read_only=True)

    class Meta:
        model = StudyNote
        fields = (
            "id",
            "group_id",
            "title",
            "content",
            "ai_summary",
            "author",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class StudyNoteSummarySerializer(serializers.ModelSerializer[StudyNote]):
    """노트 요약 전용 Serializer"""

    group_id = serializers.IntegerField(source="study_group_id", read_only=True)

    class Meta:
        model = StudyNote
        fields = ("id", "group_id", "title", "ai_summary", "updated_at")
        read_only_fields = fields
