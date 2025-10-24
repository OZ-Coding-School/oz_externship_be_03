from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
from apps.studies.models.notes import StudyNote
from apps.studies.serializers.notes import (
    StudyNoteCreateSerializer,
    StudyNoteDetailSerializer,
    StudyNoteListItemSerializer,
    StudyNoteSummarySerializer,
    StudyNoteUpdateSerializer,
)


class StudyNoteListCreateAPIView(APIView):
    """
    스터디 노트 생성 및 목록 조회 API
    """

    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(summary="스터디 노트 생성 API")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group_id = kwargs.get("group_id")
        group = get_object_or_404(StudyGroup, uuid=self.kwargs["group_id"])

        serializer = StudyNoteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": 400,
                    "message": "유효성 검사에 실패했습니다.",
                    "error": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        note = serializer.save(
            author=request.user if request.user.is_authenticated else None,
            study_group=group,
        )
        return Response(
            {
                "status": 201,
                "message": "노트가 성공적으로 생성되었습니다.",
                "data": StudyNoteDetailSerializer(note).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="스터디 노트 목록 조회 API")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group_id = kwargs.get("group_id")
        group = get_object_or_404(StudyGroup, uuid=self.kwargs["group_id"])

        notes = (  # N+1 미연에 방지
            StudyNote.objects.filter(study_group=group)
            .select_related("author")
            .prefetch_related("attachments", "images")
            .order_by("-created_at")
        )
        serializer = StudyNoteListItemSerializer(notes, many=True)

        return Response(
            {
                "status": 200,
                "message": "노트 목록을 성공적으로 조회했습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class StudyNoteDetailAPIView(APIView):
    """
    노트 단일 조회, 수정, 삭제 API (UUID 기반)
    """

    permission_classes = [AllowAny]

    @extend_schema(summary="스터디 노트 단일 조회 API")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group_uuid = kwargs.get("group_id")
        note_id = kwargs.get("note_id")

        # group_id → uuid 기반으로 StudyGroup 조회
        group = get_object_or_404(StudyGroup, uuid=group_uuid)
        note = get_object_or_404(StudyNote, id=note_id, study_group=group)

        serializer = StudyNoteDetailSerializer(note)
        return Response(
            {
                "status": 200,
                "message": "노트를 성공적으로 조회했습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(summary="스터디 노트 수정 API")
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group_uuid = kwargs.get("group_id")
        note_id = kwargs.get("note_id")

        group = get_object_or_404(StudyGroup, uuid=group_uuid)
        note = get_object_or_404(StudyNote, id=note_id, study_group=group)

        if note.author != request.user:
            raise PermissionDenied("해당 노트를 수정할 권한이 없습니다.")

        serializer = StudyNoteUpdateSerializer(note, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {
                    "status": 400,
                    "message": "입력값 검증에 실패했습니다.",
                    "error": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = serializer.save()
        return Response(
            {
                "status": 200,
                "message": "노트가 성공적으로 수정되었습니다.",
                "data": StudyNoteDetailSerializer(updated).data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(summary="스터디 노트 삭제 API")
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group_uuid = kwargs.get("group_id")
        note_id = kwargs.get("note_id")

        group = get_object_or_404(StudyGroup, uuid=group_uuid)
        note = get_object_or_404(StudyNote, id=note_id, study_group=group)

        if note.author != request.user:
            raise PermissionDenied("해당 노트를 삭제할 권한이 없습니다.")

        note.delete()
        return Response(
            {
                "status": 204,
                "message": "노트가 성공적으로 삭제되었습니다.",
                "data": None,
            },
            status=status.HTTP_204_NO_CONTENT,
        )


class StudyNoteSummaryAPIView(APIView):
    """
    노트 요약 조회 API (Mock)
    """

    permission_classes = [AllowAny]

    @extend_schema(summary="스터디 노트 요약 조회 API")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group_id = kwargs.get("group_id")
        note_id = kwargs.get("note_id")

        note = get_object_or_404(StudyNote, id=note_id, study_group_id=group_id)
        serializer = StudyNoteSummarySerializer(note)
        return Response(
            {
                "status": 200,
                "message": "요약 정보를 성공적으로 조회했습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
