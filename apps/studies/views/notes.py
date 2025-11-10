from __future__ import annotations

import logging
from typing import Union
from uuid import UUID

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import (
    BasePermission,
    DjangoObjectPermissions,
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.notes import StudyNote
from apps.studies.permissions import IsGroupMember, IsStudyNoteAuthor
from apps.studies.serializers.notes import (
    StudyNoteCreateSerializer,
    StudyNoteDetailSerializer,
    StudyNoteListItemSerializer,
    StudyNoteUpdateSerializer,
)
from apps.studies.tasks import generate_ai_summary_task

logger = logging.getLogger(__name__)


class StudyNoteListAPIView(APIView):
    """
    스터디 노트 목록 조회 API
    """

    permission_classes = [IsAuthenticated, IsGroupMember]

    @extend_schema(summary="스터디 노트 목록 조회 API")
    def get(self, request: Request, group_uuid: UUID) -> Response:
        notes = (
            StudyNote.objects.filter(study_group__uuid=group_uuid)
            .select_related("author")  # 각 그룹별 노트리스트이기 때문에 그룹ID필드 제거
            .prefetch_related("attachments")
            .annotate(files_count=Count("attachments", distinct=True))
            .order_by("-created_at")
        )
        serializer = StudyNoteListItemSerializer(notes, many=True)
        return Response(
            {
                "status": status.HTTP_200_OK,
                "message": "노트 목록을 성공적으로 조회했습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class StudyNoteCreateAPIView(APIView):
    """
    스터디 노트 목록 생성 API
    """

    permission_classes = [IsAuthenticated, IsGroupMember]

    @extend_schema(summary="스터디 노트 생성 API")
    def post(self, request: Request) -> Response:
        # IsGroupMember.has_permission() 통과 시, view._group 이 주입되어 있음
        serializer = StudyNoteCreateSerializer(
            data=request.data,
            context={"request": request, "view": self},
        )
        serializer.is_valid(raise_exception=True)

        self.check_object_permissions(request, serializer.validated_data["study_group"])

        note = serializer.save()

        # 비동기 AI 요약 생성 (Celery)
        # 작성된 노트의 ID를 태스크 큐에 전달하여 Gemini 요약문 생성 및 DB 저장 수행
        try:
            generate_ai_summary_task.delay(note.id)
        except Exception as e:
            logger.error(
                "[NoteCreate] AI 요약 비동기 호출 실패: note_id=%s, error=%s", note.id, e, exc_info=True
            )  # ex) [NoteCreate] AI 요약 비동기호출 실패 : "1", "{e}" 레이즈 방식이라 가볍고 모든 걸 str로 타입변환

        return Response(
            {
                "status": status.HTTP_201_CREATED,
                "message": "노트가 성공적으로 생성되었습니다.",
                "data": StudyNoteDetailSerializer(note).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StudyNoteDetailAPIView(APIView):
    """
    노트 단일 조회, 수정, 삭제 API
    - GET: [IsAuthenticated, IsGroupMember]
    - PATCH/DELETE: [IsAuthenticated, IsGroupMember, IsStudyNoteAuthor]
    """

    permission_classes = [IsAuthenticated, IsGroupMember, IsStudyNoteAuthor]

    def get_permissions(self) -> list[Union[BasePermission, DjangoObjectPermissions]]:
        """HTTP 메서드별 권한 분기"""
        if self.request.method not in ("PATCH", "DELETE"):
            return [IsAuthenticated(), IsGroupMember()]
        return [IsAuthenticated(), IsGroupMember(), IsStudyNoteAuthor()]

    def _get_note(self, note_id: int) -> StudyNote:
        return get_object_or_404(
            StudyNote.objects.select_related("author", "study_group").prefetch_related("attachments", "images"),
            id=note_id,
        )

    @extend_schema(summary="스터디 노트 단일 조회 API")
    def get(self, request: Request, note_id: int) -> Response:
        note = self._get_note(note_id)

        self.check_object_permissions(request, obj=note.study_group)

        serializer = StudyNoteDetailSerializer(note)
        return Response(
            {
                "status": status.HTTP_200_OK,
                "message": "노트를 성공적으로 조회했습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(summary="스터디 노트 수정 API")
    def patch(self, request: Request, note_id: int) -> Response:
        note = self._get_note(note_id)
        self.check_object_permissions(request, obj=note.study_group)

        serializer = StudyNoteUpdateSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_note = serializer.save()

        # content에 실제 변경이 일어난 경우에만 AI 요약 재생성
        # 요구사항엔 없지만 필요하다고 생각돼서 추가
        if "content" in serializer.validated_data:
            try:
                generate_ai_summary_task.delay(updated_note.id, force=True)
            except Exception as e:
                logger.error(
                    "[NoteUpdate] AI 요약 재생성 실패: note_id=%s, error=%s",
                    updated_note.id,
                    e,
                    exc_info=True,
                )

        return Response(
            {
                "status": status.HTTP_200_OK,
                "message": "노트가 성공적으로 수정되었습니다.",
                "data": StudyNoteDetailSerializer(updated_note).data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(summary="스터디 노트 삭제 API")
    def delete(self, request: Request, note_id: int) -> Response:
        note = self._get_note(note_id)
        self.check_object_permissions(request, obj=note.study_group)
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
