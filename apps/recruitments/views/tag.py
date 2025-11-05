from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.recruitments.models import RecruitmentTag, Tag
from apps.recruitments.serializers.tag import TagSerializer


class TagPagination(PageNumberPagination):
    """태그 목록 페이지네이션 설정"""

    page_size: int = 5
    page_size_query_param: str = "page_size"
    max_page_size: int = 50


@extend_schema(
    tags=["RecruitmentTags"],
    parameters=[
        OpenApiParameter(
            name="recruitment_id",
            type=int,
            location=OpenApiParameter.PATH,
            description="공고 ID (URL 경로에서 전달됨)",
            required=True,
        ),
        OpenApiParameter(
            name="q",
            type=str,
            location=OpenApiParameter.QUERY,
            description="태그명 검색 키워드 (부분 일치 검색)",
            required=False,
        ),
    ],
)
class RecruitmentTagListCreateView(generics.ListCreateAPIView[Tag]):
    """특정 공고의 태그 목록 조회 및 신규 태그 등록 API"""

    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = TagPagination

    def get_queryset(self) -> Any:
        """특정 공고에 연결된 태그 목록 조회 (검색 포함)"""
        recruitment_id = self.kwargs.get("recruitment_id")
        if recruitment_id is None:
            return Tag.objects.none()

        q = self.request.query_params.get("q", "").strip()
        queryset = Tag.objects.filter(recruitment_tags__recruitment_id=recruitment_id).order_by("id")
        if q:
            queryset = queryset.filter(name__icontains=q)
        return queryset

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """페이지네이션 직접 적용 (page_size 반영 보장)"""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """기존 태그 재사용 및 RecruitmentTag 연결 생성"""
        recruitment_id = self.kwargs.get("recruitment_id")
        if not recruitment_id:
            return Response(
                {"detail": "URL에 recruitment_id가 누락되었습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name: str = serializer.validated_data["name"]

        existing_tag = Tag.objects.filter(name__iexact=name).first()
        if existing_tag:
            tag = existing_tag
        else:
            tag = Tag.objects.create(name=name)

        # 이미 연결되어 있으면 400 반환
        if RecruitmentTag.objects.filter(recruitment_id=recruitment_id, tag=tag).exists():
            return Response(
                {"detail": "이미 이 공고에 연결된 태그입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        RecruitmentTag.objects.create(recruitment_id=recruitment_id, tag=tag)
        return Response(
            self.get_serializer(tag).data,
            status=status.HTTP_201_CREATED,
        )
