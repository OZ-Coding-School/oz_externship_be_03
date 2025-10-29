import uuid
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

    # Mock 제약(중복/존재하지 않음) — 팀의 Bookmark 패턴과 동일하게 유지
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
        # Mock 데이터: 실제 DB 접근 없이 모델 인스턴스를 메모리에 구성 (팀 패턴과 동일)
        mock_data = [
            RecruitmentAttachment(
                id=i,
                recruitment_id=recruitment_id,
                file_url=f"https://cdn.example.com/files/mock_{i}.pdf",
                file_name=f"Mock 파일 {i}.pdf",
                created_at=timezone.now() - timedelta(days=i),
                updated_at=timezone.now(),
            )
            for i in range(1, 16)
        ]
        serializer = self.serializer_class(mock_data, many=True)

        # 수동 페이지네이션 (Bookmark와 동일한 10개 페이징)
        page = int(request.query_params.get("page", 1))
        page_size = 10
        start, end = (page - 1) * page_size, (page - 1) * page_size + page_size
        paged_data = serializer.data[start:end]

        return Response({"results": paged_data}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Attachments"],
        summary="첨부파일 생성 API",
        request=AttachmentSerializer,
        responses={201: AttachmentSerializer},
        operation_id="v1_attachments_create",
    )
    def post(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        data = request.data

        # recruitment 유효성 (Mock)
        if recruitment_id in self.MOCK_NONEXISTENT_RECRUITMENT_IDS:
            return Response({"detail": "존재하지 않는 공고입니다."}, status=status.HTTP_404_NOT_FOUND)

        # 중복 URL 체크 (Mock)
        if (url := data.get("file_url")) in self.MOCK_DUPLICATE_URLS:
            return Response({"detail": "이미 등록된 첨부파일입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 스키마 일치 및 유효성 확인 (Mock이지만 팀 코드와 동일하게 serializer.is_valid 사용)
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        # 생성 결과(Mock) — id만 임의 값으로 반환
        created = RecruitmentAttachment(
            id=uuid.uuid4().int % 100000,  # 임의 id
            recruitment_id=recruitment_id,
            file_url=serializer.validated_data["file_url"],
            file_name=serializer.validated_data["file_name"],
            created_at=timezone.now(),
            updated_at=timezone.now(),
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
        mock = RecruitmentAttachment(
            id=attachment_id,
            recruitment_id=1,
            file_url=f"https://cdn.example.com/files/mock_{attachment_id}.pdf",
            file_name=f"Mock 파일 {attachment_id}.pdf",
            created_at=timezone.now() - timedelta(days=1),
            updated_at=timezone.now(),
        )
        return Response(self.serializer_class(mock).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Attachments"],
        summary="첨부파일 삭제 API",
        operation_id="v1_attachments_destroy",
    )
    def delete(self, request: Request, attachment_id: int, *args: Any, **kwargs: Any) -> Response:
        # 팀 코드 스타일에 맞춰 204와 메시지를 함께 반환
        return Response({"detail": "첨부파일이 삭제되었습니다."}, status=status.HTTP_200_OK)
