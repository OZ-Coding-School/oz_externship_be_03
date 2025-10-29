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

from apps.recruitments.models.recruitment_images import RecruitmentImage
from apps.recruitments.serializers.images import ImagesSerializer


class ImageListCreateAPIView(APIView):
    """
    GET  /api/v1/recruitments/<int:recruitment_id>/images/
    POST /api/v1/recruitments/<int:recruitment_id>/images/
    """

    serializer_class = ImagesSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    MOCK_DUPLICATE_URLS = {
        "https://cdn.example.com/imgs/dup1.jpg",
        "https://cdn.example.com/imgs/dup2.jpg",
    }
    MOCK_NONEXISTENT_RECRUITMENT_IDS = {9999, 8888}

    @extend_schema(
        tags=["Images"],
        summary="이미지 목록 조회 API",
        responses={200: ImagesSerializer(many=True)},
        operation_id="v1_images_list",
    )
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        mock_data = [
            RecruitmentImage(
                id=i,
                recruitment_id=recruitment_id,
                img_url=f"https://cdn.example.com/imgs/mock_{i}.jpg",
                created_at=timezone.now() - timedelta(days=i),
                updated_at=timezone.now(),
            )
            for i in range(1, 16)
        ]
        serializer = self.serializer_class(mock_data, many=True)

        page = int(request.query_params.get("page", 1))
        page_size = 10
        start, end = (page - 1) * page_size, (page - 1) * page_size + page_size
        paged_data = serializer.data[start:end]

        return Response({"results": paged_data}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Images"],
        summary="이미지 생성 API",
        request=ImagesSerializer,
        responses={201: ImagesSerializer},
        operation_id="v1_images_create",
    )
    def post(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        data = request.data

        if recruitment_id in self.MOCK_NONEXISTENT_RECRUITMENT_IDS:
            return Response({"detail": "존재하지 않는 공고입니다."}, status=status.HTTP_400_BAD_REQUEST)

        if (url := data.get("img_url")) in self.MOCK_DUPLICATE_URLS:
            return Response({"detail": "이미 등록된 이미지입니다."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        created = RecruitmentImage(
            id=uuid.uuid4().int % 100000,
            recruitment_id=recruitment_id,
            img_url=serializer.validated_data["img_url"],
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return Response(self.serializer_class(created).data, status=status.HTTP_201_CREATED)


class ImageRetrieveDestroyAPIView(APIView):
    """
    GET    /api/v1/images/<int:image_id>/
    DELETE /api/v1/images/<int:image_id>/
    """

    serializer_class = ImagesSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(
        tags=["Images"],
        summary="이미지 상세 조회 API",
        responses={200: ImagesSerializer},
        operation_id="v1_images_retrieve",
    )
    def get(self, request: Request, image_id: int, *args: Any, **kwargs: Any) -> Response:
        mock = RecruitmentImage(
            id=image_id,
            recruitment_id=1,
            img_url=f"https://cdn.example.com/imgs/mock_{image_id}.jpg",
            created_at=timezone.now() - timedelta(days=1),
            updated_at=timezone.now(),
        )
        return Response(self.serializer_class(mock).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Images"],
        summary="이미지 삭제 API",
        operation_id="v1_images_destroy",
    )
    def delete(self, request: Request, image_id: int, *args: Any, **kwargs: Any) -> Response:
        return Response({"detail": "이미지가 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)
