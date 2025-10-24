from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.studies.models.notes import StudyNote

User = get_user_model()


class StudyNoteAuthorSerializer(serializers.ModelSerializer[Any]):
    """작성자 최소 정보 직렬화"""

    class Meta:
        model = User
        fields = ("id", "nickname")


class StudyNoteCreateSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 생성용 Serializer
    - view에서 `study_group`을 주입
    """

    class Meta:
        model = StudyNote
        fields = ("title", "content", "study_group")

    def create(self, validated_data: dict[str, Any]) -> StudyNote:
        """
        view에서 author / study_group을 주입
        """
        return StudyNote.objects.create(**validated_data)


class StudyNoteUpdateSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 수정용 Serializer
    - PATCH 기반 partial 수정만 수행
    """

    class Meta:
        model = StudyNote
        fields = ("title", "content", "study_group")  # mock 단계 일단 필드추가


class StudyNoteListItemSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 목록 Serializer
    - group_uuid 제거 (URL 단순화)
    - author 정보만 최소화 노출
    """

    author = StudyNoteAuthorSerializer(read_only=True)

    class Meta:
        model = StudyNote
        fields = (
            "id",
            "title",
            "ai_summary",
            "author",
            "created_at",
            "study_group",
        )
        read_only_fields = fields


class StudyNoteDetailSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 단일 조회 Serializer
    - 그룹 UUID 제거
    - 작성자 및 요약 정보 포함
    """

    author = StudyNoteAuthorSerializer(read_only=True)

    class Meta:
        model = StudyNote
        fields = (
            "id",
            "title",
            "content",
            "ai_summary",
            "author",
            "created_at",
            "updated_at",
            "study_group",
        )
        read_only_fields = fields


class StudyNoteSummarySerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 요약 전용 Serializer
    - 그룹 정보 제거
    """

    class Meta:
        model = StudyNote
        fields = (
            "id",
            "title",
            "content",
            "ai_summary",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
