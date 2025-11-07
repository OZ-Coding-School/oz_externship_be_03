from __future__ import annotations

from uuid import UUID

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import (  # 전환 시 IsAuthenticated 로 교체
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models import StudyGroup
from apps.studies.models.notes import StudyNote
from apps.studies.permissions import IsGroupMember, IsStudyNoteAuthor  # 생성 시 사용

# from apps.studies.permissions import IsStudyNoteAuthor  # Detail 뷰 전환 시 활성화
from apps.studies.serializers.notes import (
    StudyNoteCreateSerializer,
    StudyNoteDetailSerializer,
    StudyNoteListItemSerializer,
    StudyNoteUpdateSerializer,
)

# from apps.studies.services.notes import StudyNoteService # AI요약 관련 사용 때 주석해제


class StudyNoteListAPIView(APIView):
    """
    스터디 노트 목록 조회 API

    - GET: 정책상 공개(지금은 AllowAny) 추후 IsAuthenticated 로 교체
    """

    permission_classes = [IsAuthenticated, IsGroupMember]  # 나중엔 [IsAuthenticated, IsGroupMember]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]  # S3 도입 후 정리

    @extend_schema(summary="스터디 노트 목록 조회 API")
    def get(self, request: Request, group_uuid: UUID) -> Response:
        notes = (
            StudyNote.objects.filter(study_group__uuid=group_uuid)
            .select_related("author", "study_group")
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

    - POST: IsGroupMember.has_permission() 에서 group_uuid 기반 멤버 검증 + view._group 주입
    """

    permission_classes = [IsAuthenticated, IsGroupMember]  # 나중엔 [IsAuthenticated, IsGroupMember]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]  # S3 도입 후 정리

    @extend_schema(summary="스터디 노트 생성 API")
    def post(self, request: Request) -> Response:
        # IsGroupMember.has_permission() 통과 시, view._group 이 주입되어 있음
        serializer = StudyNoteCreateSerializer(
            data=request.data,
            context={"request": request, "view": self},
        )
        serializer.is_valid(raise_exception=True)

        self.check_object_permissions(request, serializer.validated_data["study_group"])

        serializer.save()  # author HiddenField, study_group은 validate()에서 주입

        return Response(
            {
                "status": status.HTTP_201_CREATED,
                "message": "노트가 성공적으로 생성되었습니다.",
                "data": StudyNoteDetailSerializer(serializer.instance).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StudyNoteDetailAPIView(APIView):
    """
    노트 단일 조회, 수정, 삭제 API
    - 지금은 AllowAny 추후:
      * GET: [IsAuthenticated, IsGroupMember]
      * PATCH/DELETE: [IsAuthenticated, IsGroupMember, IsStudyNoteAuthor]
    """

    permission_classes = [IsAuthenticated, IsGroupMember]  # 추후 교체
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]  # S3 도입 후 정리

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
