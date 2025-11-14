from __future__ import annotations

import logging
from typing import Any, Optional, Sequence, cast
from uuid import UUID

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
from apps.studies.models.notes import StudyNote
from apps.studies.permissions import IsGroupMember, IsStudyNoteAuthor
from apps.studies.serializers.notes import (
    StudyNoteCreateSerializer,
    StudyNoteDetailSerializer,
    StudyNoteListItemSerializer,
    StudyNoteUpdateSerializer,
)

# from apps.studies.services.notes import StudyNoteAIService  # ❌ 비활성화: AI 서비스 import 제거

logger = logging.getLogger(__name__)


# 5팀 응답 규약 믹신
class BaseResponseMixin:
    def success(self, message: str, data: Optional[Any] = None, code: int = status.HTTP_200_OK) -> Response:
        return Response({"status": code, "message": message, "data": data}, status=code)

    def no_content(self) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudyNoteListAPIView(BaseResponseMixin, APIView):
    """
    스터디 노트 목록 조회 API
    """

    permission_classes = [IsAuthenticated, IsGroupMember]

    @extend_schema(tags=["StudyGroupNote"], summary="스터디 노트 목록 조회 API")
    def get(self, request: Request, group_uuid: UUID) -> Response:
        notes = (
            StudyNote.objects.filter(study_group__uuid=group_uuid)
            .select_related("author")
            .annotate(files_count=Count("attachments", distinct=True))
            .order_by("-created_at")
        )
        serializer = StudyNoteListItemSerializer(cast(Sequence[StudyNote], notes), many=True)
        return self.success(
            "노트 목록을 성공적으로 조회했습니다.",
            serializer.data,
        )


class StudyNoteCreateAPIView(BaseResponseMixin, APIView):
    """
    스터디 노트 생성 API
    """

    permission_classes = [IsAuthenticated, IsGroupMember]

    @extend_schema(tags=["StudyGroupNote"], summary="스터디 노트 생성 API")
    def post(self, request: Request) -> Response:
        serializer = StudyNoteCreateSerializer(
            data=request.data,
            context={"request": request, "view": self},
        )
        serializer.is_valid(raise_exception=True)
        self.check_object_permissions(request, serializer.validated_data["study_group"])

        note = serializer.save()

        # ----------------------------------------------------------------------
        # ❌ Gemini 요약 기능 완전 비활성화
        # try:
        #     StudyNoteAIService.summarize(note)
        # except Exception as e:
        #     logger.error("[NoteCreate] AI 요약 생성 실패: note_id=%s, error=%s", note.id, e, exc_info=True)
        # ----------------------------------------------------------------------

        return self.success(
            "노트가 성공적으로 생성되었습니다.",
            StudyNoteDetailSerializer(note).data,
            code=status.HTTP_201_CREATED,
        )


class StudyNoteDetailAPIView(BaseResponseMixin, APIView):
    """
    노트 단일 조회, 수정, 삭제 API
    """

    permission_classes = [IsAuthenticated, IsGroupMember, IsStudyNoteAuthor]

    def get_permissions(self) -> list[BasePermission]:
        """메서드별 다른 권한 적용"""
        if self.request.method == "GET":
            return [IsAuthenticated(), IsGroupMember()]
        return [IsAuthenticated(), IsGroupMember(), IsStudyNoteAuthor()]

    def _get_note(self, note_id: int) -> StudyNote:
        return get_object_or_404(
            StudyNote.objects.select_related("author", "study_group").prefetch_related("attachments", "images"),
            id=note_id,
        )

    def _check_group_member_permission(self, request: Request, study_group: StudyGroup) -> None:
        if not IsGroupMember().has_object_permission(request, self, study_group):
            self.permission_denied(request, message="스터디 그룹 멤버만 접근할 수 있습니다.")

    def _check_note_author_permission(self, request: Request, note: StudyNote) -> None:
        if not IsStudyNoteAuthor().has_object_permission(request, self, note):
            self.permission_denied(request, message="해당 노트를 수정 또는 삭제할 권한이 없습니다.")

    @extend_schema(tags=["StudyGroupNote"], summary="스터디 노트 단일 조회 API")
    def get(self, request: Request, note_id: int) -> Response:
        note = self._get_note(note_id)
        self._check_group_member_permission(request, note.study_group)
        serializer = StudyNoteDetailSerializer(note)
        return self.success("노트를 성공적으로 조회했습니다.", serializer.data)

    @extend_schema(tags=["StudyGroupNote"], summary="스터디 노트 수정 API")
    def patch(self, request: Request, note_id: int) -> Response:
        note = self._get_note(note_id)
        self._check_group_member_permission(request, note.study_group)
        self._check_note_author_permission(request, note)

        serializer = StudyNoteUpdateSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_note = serializer.save()

        # ----------------------------------------------------------------------
        # ❌ Gemini 요약 재생성 기능 비활성화
        # if "content" in serializer.validated_data:
        #     try:
        #         StudyNoteAIService.summarize(updated_note)
        #     except Exception as e:
        #         logger.error("[NoteUpdate] AI 요약 재생성 실패: note_id=%s, error=%s", updated_note.id, e, exc_info=True)
        # ----------------------------------------------------------------------

        return self.success("노트가 성공적으로 수정되었습니다.", StudyNoteDetailSerializer(updated_note).data)

    @extend_schema(tags=["StudyGroupNote"], summary="스터디 노트 삭제 API")
    def delete(self, request: Request, note_id: int) -> Response:
        note = self._get_note(note_id)
        self._check_group_member_permission(request, note.study_group)
        self._check_note_author_permission(request, note)
        note.delete()
        return self.no_content()
