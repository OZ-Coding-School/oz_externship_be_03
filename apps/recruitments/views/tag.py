from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.serializers.tag import TagSerializer


@extend_schema(tags=["RecruitmentTags"])
class TagListView(APIView):
    """전체 태그(Mock) 목록 조회 및 생성"""

    permission_classes = [AllowAny]
    serializer_class = TagSerializer

    MOCK_TAGS: list[dict[str, str]] = [
        {"id": "1", "name": "Python"},
        {"id": "2", "name": "Django"},
        {"id": "3", "name": "JavaScript"},
        {"id": "4", "name": "AI"},
        {"id": "5", "name": "Frontend"},
        {"id": "6", "name": "React"},
        {"id": "7", "name": "Vue"},
    ]

    class Pagination(PageNumberPagination):
        page_size = 3  # 한 페이지에 3개씩 표시

    @extend_schema(
        summary="전체 태그 목록 조회 (Mock, 페이지네이션 포함)",
        description="전체 태그(Mock 데이터)를 페이지네이션과 함께 반환합니다.",
        responses={200: TagSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """전체 태그(Mock) 목록 조회 (페이지네이션 포함)"""
        paginator = self.Pagination()

        # paginate_queryset()은 None을 반환할 수도 있어 안전한 처리 필요
        page: list[dict[str, str]] | None = paginator.paginate_queryset(self.MOCK_TAGS, request)  # type: ignore[arg-type]
        if page is None:
            page = self.MOCK_TAGS  # fallback (페이지네이션 비활성 시)

        serializer = TagSerializer(page, many=True)  # type: ignore[arg-type]
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="새로운 태그 생성 (Mock)",
        description="입력된 이름으로 새로운 태그(Mock)를 생성합니다. 시리얼라이저를 통한 검증 포함.",
        request=TagSerializer,
        responses={
            201: TagSerializer,
            400: {"example": {"detail": "태그 이름은 필수입니다."}},
        },
    )
    def post(self, request: Request) -> Response:
        """새로운 태그(Mock) 생성 (시리얼라이저 검증 적용)"""
        serializer = TagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name: str = serializer.validated_data["name"]

        # 중복 검사
        if any(tag["name"].lower() == name.lower() for tag in self.MOCK_TAGS):
            return Response(
                {"detail": "이미 존재하는 태그입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 새로운 태그 생성 (Mock)
        new_tag: dict[str, Any] = {"id": str(len(self.MOCK_TAGS) + 1), "name": name}
        return Response(new_tag, status=status.HTTP_201_CREATED)
