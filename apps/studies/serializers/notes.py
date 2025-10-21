from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.studies.models.notes import StudyNote

User = get_user_model()

__all__ = [
    "AuthorSlimSerializer",
    "SummaryMetaSerializer",
    "StudyNoteCreateSerializer",
    "StudyNoteUpdateSerializer",
    "StudyNoteListItemSerializer",
    "StudyNoteDetailSerializer",
    "StudyNoteSummarySerializer",
]


class AuthorSlimSerializer(serializers.ModelSerializer[Any]):
    class Meta:
        model = User
        fields = ("id", "username")
        read_only_fields = fields


class SummaryMetaSerializer(serializers.Serializer[Any]):
    model = serializers.CharField(read_only=True)
    prompt_version = serializers.CharField(read_only=True)
    prompt_hash = serializers.CharField(read_only=True)
    input_tokens = serializers.IntegerField(read_only=True)
    output_tokens = serializers.IntegerField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)
    error = serializers.CharField(read_only=True, allow_null=True, required=False)


class StudyNoteCreateSerializer(serializers.ModelSerializer[StudyNote]):
    class Meta:
        model = StudyNote
        fields = ("id", "title", "content")
        read_only_fields = ("id",)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs.get("title"):
            raise serializers.ValidationError({"title": "필수 항목입니다."})
        if not attrs.get("content"):
            raise serializers.ValidationError({"content": "필수 항목입니다."})
        if "group" not in self.context:
            raise serializers.ValidationError("내부 오류: group context가 누락되었습니다.")
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> StudyNote:
        if "author" not in self.context or "group" not in self.context:
            raise serializers.ValidationError("생성 실패: 권한 또는 컨텍스트가 유효하지 않습니다.")
        note: StudyNote = super().create(validated_data)
        return note


class StudyNoteUpdateSerializer(serializers.ModelSerializer[StudyNote]):
    class Meta:
        model = StudyNote
        fields = ("title", "content")
        extra_kwargs = {"title": {"required": False}, "content": {"required": False}}

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("title 또는 content 중 하나는 필요합니다.")
        return attrs


class StudyNoteListItemSerializer(serializers.ModelSerializer[StudyNote]):
    author = AuthorSlimSerializer(read_only=True)

    class Meta:
        model = StudyNote
        fields = ("id", "title", "summary", "author", "created_at")
        read_only_fields = fields


class StudyNoteDetailSerializer(serializers.ModelSerializer[StudyNote]):
    author = AuthorSlimSerializer(read_only=True)
    group_id = serializers.IntegerField(source="study_group_id", read_only=True)
    summary_meta = SummaryMetaSerializer(source="summary_meta", read_only=True)

    class Meta:
        model = StudyNote
        fields = (
            "id",
            "group_id",
            "title",
            "content",
            "summary",
            "summary_meta",
            "author",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class StudyNoteSummarySerializer(serializers.ModelSerializer[StudyNote]):
    group_id = serializers.IntegerField(source="study_group_id", read_only=True)
    summary_meta = SummaryMetaSerializer(source="summary_meta", read_only=True)

    class Meta:
        model = StudyNote
        fields = ("id", "group_id", "title", "summary", "summary_meta", "updated_at")
        read_only_fields = fields