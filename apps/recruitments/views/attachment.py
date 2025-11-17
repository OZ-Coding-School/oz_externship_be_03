from datetime import timedelta
from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.attachment import RecruitmentAttachment
from apps.recruitments.serializers.attachment import AttachmentSerializer


class AttachmentListCreateAPIView(APIView):
    """
    GET  /api/v1/recruitments/<int:recruitment_id>/attachments/
    POST /api/v1/recruitments/<int:recruitment_id>/attachments/
    """

    serializer_class = AttachmentSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    # Mock 제약(중복/존재하지 않음)
    MOCK_DUPLICATE_URLS = {
        "https://cdn.example.com/files/dup1.pdf",
        "https://cdn.example.com/files/dup2.pdf",
    }
    MOCK_NONEXISTENT_RECRUITMENT_IDS = {9999, 8888}

    @extend_schema(
        tags=["Attachments"],
        summary="첨부파일 목록 조회 API",
        responses={200: AttachmentSerializer(many=True)},
        operation_id="v1_attachments_list",
    )
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        base_now = timezone.now()
        mock_data = [
            RecruitmentAttachment(
                id=i,
                recruitment_id=recruitment_id,
                file_url=f"https://cdn.example.com/files/mock_{i}.pdf",
                file_name=f"Mock 파일 {i}.pdf",
                created_at=base_now - timedelta(days=i),
                updated_at=base_now,
            )
            for i in range(1, 16)
        ]

        try:
            page = int(request.query_params.get("page", 1))
            if page < 1:
                page = 1
        except (TypeError, ValueError):
            page = 1

        page_size = 10
        start, end = (page - 1) * page_size, (page - 1) * page_size + page_size
        page_objs = mock_data[start:end]
        serializer = self.serializer_class(page_objs, many=True)

        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Attachments"],
        summary="첨부파일 생성 API",
        request=AttachmentSerializer,
        responses={201: AttachmentSerializer},
        operation_id="v1_attachments_create",
    )
    def post(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        data = request.data

        if recruitment_id in self.MOCK_NONEXISTENT_RECRUITMENT_IDS:
            return Response({"detail": "존재하지 않는 공고입니다."}, status=status.HTTP_404_NOT_FOUND)

        url = data.get("file_url")
        if isinstance(url, str):
            url = url.strip()
            data["file_url"] = url

        if url in self.MOCK_DUPLICATE_URLS:
            return Response({"detail": "이미 등록된 첨부파일입니다."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        base_now = timezone.now()
        created = RecruitmentAttachment(
            id=1,  # uuid 대신 고정 id
            recruitment_id=recruitment_id,
            file_url=serializer.validated_data["file_url"],
            file_name=serializer.validated_data["file_name"],
            created_at=base_now,
            updated_at=base_now,
        )
        return Response(self.serializer_class(created).data, status=status.HTTP_201_CREATED)


class AttachmentRetrieveDestroyAPIView(APIView):
    """
    GET    /api/v1/attachments/<int:attachment_id>/
    DELETE /api/v1/attachments/<int:attachment_id>/
    """

    serializer_class = AttachmentSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(
        tags=["Attachments"],
        summary="첨부파일 상세 조회 API",
        responses={200: AttachmentSerializer},
        operation_id="v1_attachments_retrieve",
    )
    def get(self, request: Request, attachment_id: int, *args: Any, **kwargs: Any) -> Response:
        base_now = timezone.now()
        mock = RecruitmentAttachment(
            id=attachment_id,
            recruitment_id=1,
            file_url=f"https://cdn.example.com/files/mock_{attachment_id}.pdf",
            file_name=f"Mock 파일 {attachment_id}.pdf",
            created_at=base_now - timedelta(days=1),
            updated_at=base_now,
        )
        return Response(self.serializer_class(mock).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Attachments"],
        summary="첨부파일 삭제 API",
        operation_id="v1_attachments_destroy",
    )
    def delete(self, request: Request, attachment_id: int, *args: Any, **kwargs: Any) -> Response:
        return Response({"detail": "첨부파일이 삭제되었습니다."}, status=status.HTTP_200_OK)
