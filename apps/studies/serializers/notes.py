from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.studies.models import StudyGroup
from apps.studies.models.notes import StudyNote, StudyNoteAttachment, StudyNoteImage

User = get_user_model()


class StudyNoteAuthorSerializer(serializers.ModelSerializer[Any]):
    """작성자 최소 정보 직렬화"""

    class Meta:
        model = User
        fields = ("id", "nickname", "profile_img_url")


class StudyNoteAttachmentSerializer(serializers.ModelSerializer[Any]):
    """스터디 노트 첨부파일 Serializer"""

    class Meta:
        model = StudyNoteAttachment
        fields = ("id", "file_name", "file_url", "created_at")
        read_only_fields = fields


class StudyNoteImageSerializer(serializers.ModelSerializer[Any]):
    """스터디 노트 이미지 Serializer"""

    class Meta:
        model = StudyNoteImage
        fields = ("id", "img_url", "created_at")
        read_only_fields = fields


class StudyNoteCreateSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 생성용 Serializer
    - Notes 뷰 인스턴스(self)에, 퍼미션이 찾아낸 StudyGroup 객체를 붙여둔 뒤, study_group FK로 저장
    - author HiddenField 로 현재 사용자 자동 주입
    """

    study_group = serializers.SlugRelatedField(queryset=StudyGroup.objects.all(), slug_field="uuid", write_only=True)
    author = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = StudyNote
        fields = ("title", "content", "study_group", "author")


class StudyNoteUpdateSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 수정용 Serializer
    - PATCH 기반 수정만
    """

    class Meta:
        model = StudyNote
        fields = ("title", "content")  # study_group 이동시키는 수정은 아니라고 생각돼서 필드에서 제거


class StudyNoteListItemSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 목록 Serializer
    - author 최소 정보
    - files_count: 이미지+첨부 총합(annotate로 주입)
    """

    author = StudyNoteAuthorSerializer(read_only=True)
    files_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M")

    class Meta:
        model = StudyNote
        fields = (
            "id",
            "title",
            "author",
            "created_at",
            "files_count",
        )
        read_only_fields = fields


class StudyNoteDetailSerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 단일 조회 Serializer
    """

    author = StudyNoteAuthorSerializer(read_only=True)
    attachments = StudyNoteAttachmentSerializer(many=True, read_only=True)
    images = StudyNoteImageSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M")
    updated_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M")

    class Meta:
        model = StudyNote
        fields = (
            "id",
            "title",
            "content",
            "author",
            "study_group",
            "attachments",
            "images",
            "created_at",
            "updated_at",
            "ai_summary",
        )
        read_only_fields = fields


class StudyNoteSummarySerializer(serializers.ModelSerializer[StudyNote]):
    """
    스터디 노트 요약 전용 Serializer

    """

    # note 생성일을 기준으로 프롬프트(date_str) 사용하여 AI요약하기 때문에 때문에 타임포매팅 x created_at은 형식상 유지
    class Meta:
        model = StudyNote
        fields = (
            "id",
            "title",
            "content",
            "created_at",
            "ai_summary",
        )
        read_only_fields = fields
