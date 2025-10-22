from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
    학습 기록 생성 및 전체 목록 조회 API (Mock)
    """

    serializer_class = StudyNoteCreateSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(
        tags=["Study Notes"],
        summary="학습 기록 생성 API",
        description="스터디 그룹의 학습 기록을 생성합니다. Mock 응답을 반환.",
        request=StudyNoteCreateSerializer,
        responses={201: StudyNoteDetailSerializer},
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        mock_note = StudyNote(
            id=1,
            title=serializer.validated_data.get("title"),
            content=serializer.validated_data.get("content"),
            summary="요약이 여기에 들어갑니다.",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        out = StudyNoteDetailSerializer(mock_note).data
        return Response(out, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="v1_study_notes_list",
        tags=["Study Notes"],
        summary="학습 기록 전체 목록 조회 API",
        description="스터디 그룹 내의 모든 학습 기록 목록을 조회합니다. Mock 데이터를 반환.",
        responses={200: StudyNoteListItemSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        mock_data = [
            StudyNote(
                id=i,
                title=f"Mock Study Note {i}",
                content="Mock content for Study Note",
                summary=f"요약 내용 {i}",
                created_at=timezone.now() - timedelta(days=i),
                updated_at=timezone.now() - timedelta(days=i),
            )
            for i in range(1, 6)
        ]
        serializer = StudyNoteListItemSerializer(mock_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudyNoteRetrieveUpdateDestroyAPIView(APIView):
    """
    학습 기록 단일 조회, 수정, 삭제 API (Mock)
    """

    serializer_class = StudyNoteDetailSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(tags=["Study Notes"], summary="학습 기록 상세 조회 API", responses={200: StudyNoteDetailSerializer})
    def get(self, request: Request, note_id: int, *args: Any, **kwargs: Any) -> Response:
        mock_note = StudyNote(
            id=note_id,
            title="Mock Study Note",
            content="Mock Content",
            summary="요약 내용",
            created_at=timezone.now() - timedelta(days=1),
            updated_at=timezone.now(),
        )
        serializer = self.serializer_class(mock_note)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Study Notes"],
        summary="학습 기록 수정 API",
        request=StudyNoteUpdateSerializer,
        responses={200: StudyNoteDetailSerializer},
    )
    def put(self, request: Request, note_id: int, *args: Any, **kwargs: Any) -> Response:
        serializer = StudyNoteUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mock_note = StudyNote(
            id=note_id,
            title=serializer.validated_data.get("title", "기존 제목"),
            content=serializer.validated_data.get("content", "기존 내용"),
            summary="수정된 요약",
            created_at=timezone.now() - timedelta(days=1),
            updated_at=timezone.now(),
        )
        out = self.serializer_class(mock_note).data
        return Response(out, status=status.HTTP_200_OK)

    @extend_schema(tags=["Study Notes"], summary="학습 기록 삭제 API", responses={204: None})
    def delete(self, request: Request, note_id: int, *args: Any, **kwargs: Any) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudyNoteSummaryAPIView(APIView):
    """
    학습 기록 요약 조회 API (Mock)
    """

    serializer_class = StudyNoteSummarySerializer
    permission_classes = [AllowAny]

    @extend_schema(tags=["Study Notes"], summary="학습 기록 요약 조회 API", responses={200: StudyNoteSummarySerializer})
    def get(self, request: Request, note_id: int, *args: Any, **kwargs: Any) -> Response:
        mock_note = StudyNote(
            id=note_id,
            title="Mock Note Title",
            content="Mock Content",
            summary="요약 내용입니다.",
            created_at=timezone.now() - timedelta(days=2),
            updated_at=timezone.now(),
        )
        serializer = self.serializer_class(mock_note)
        return Response(serializer.data, status=status.HTTP_200_OK)
