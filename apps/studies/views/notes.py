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
from apps.studies.permissions import IsGroupMember
from apps.studies.serializers.notes import (
    StudyNoteCreateSerializer,
    StudyNoteDetailSerializer,
    StudyNoteListItemSerializer,
    StudyNoteUpdateSerializer,
)
from apps.studies.services.notes import StudyNoteService


class StudyNoteListCreateAPIView(APIView):
    """
    스터디 노트 목록 조회 및 생성 API
    """

    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]  # s3 구현 후 삭제할 것
    # permission_classes = [IsAuthenticated, IsGroupMember]

    @extend_schema(summary="스터디 노트 목록 조회 API")
    def get(self, request: Request) -> Response:
        notes = (
            StudyNote.objects.select_related("author", "study_group")
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

    @extend_schema(summary="스터디 노트 생성 API")
    def post(self, request: Request) -> Response:
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
        )
        return Response(
            {
                "status": 201,
                "message": "노트가 성공적으로 생성되었습니다.",
                "data": StudyNoteDetailSerializer(note).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StudyNoteDetailAPIView(APIView):
    """
    노트 단일 조회, 수정, 삭제 API (UUID 기반)
    """

    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]  # s3 구현 후 삭제할 것

    @extend_schema(summary="스터디 노트 단일 조회 API")
    def get(self, request: Request, note_id: int) -> Response:
        # group uuid가 URL 매핑에서 제거되었으므로 전달 불필요,
        # StudyNote가 FK로 StudyGroup에 연결되어 있으므로 group 접근 및 권한 검증은
        # 그 둘을 연결한 note.study_group을 통해 처리.
        note = get_object_or_404(
            StudyNote.objects.select_related("author", "study_group"),
            id=note_id,
        )

        note = StudyNoteService.summarize(note)  # AI 요약 로직 통합
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
    def patch(self, request: Request, note_id: int) -> Response:
        note = get_object_or_404(
            StudyNote.objects.select_related("author", "study_group"),
            id=note_id,
        )
        self.check_object_permissions(request, note)  # IsGroupMember 로 검증계획 지금은 다 통과

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

        updated_note = serializer.save()
        return Response(
            {
                "status": 200,
                "message": "노트가 성공적으로 수정되었습니다.",
                "data": StudyNoteDetailSerializer(updated_note).data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(summary="스터디 노트 삭제 API")
    def delete(self, request: Request, note_id: int) -> Response:
        note = get_object_or_404(
            StudyNote.objects.select_related("author", "study_group"),
            id=note_id,
        )
        self.check_object_permissions(request, note)  # PATCH 와 마찬가지로 지금은 다 통과
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
