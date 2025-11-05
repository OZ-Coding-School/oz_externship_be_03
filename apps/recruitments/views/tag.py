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
            name="q",
            type=str,
            location=OpenApiParameter.QUERY,
            description="태그명 검색 키워드 (부분 일치 검색)",
            required=False,
        ),
    ],
)
class RecruitmentTagListCreateView(generics.ListCreateAPIView[Tag]):
    """
    특정 공고의 태그 목록 조회 및 신규 태그 등록 API
    - GET: 해당 공고에 연결된 태그 목록 반환 (부분 검색 & 페이지네이션 지원)
    - POST: 태그가 존재하면 재사용, 없으면 새로 생성 후 연결
    """

    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = TagPagination

    def get_queryset(self) -> Any:
        """특정 공고에 연결된 태그 목록 조회 (검색 포함)"""
        recruitment_id = self.kwargs["recruitment_id"]
        q = self.request.query_params.get("q", "").strip()

        queryset = Tag.objects.filter(recruitment_tags__recruitment_id=recruitment_id).order_by("id")

        if q:
            queryset = queryset.filter(name__icontains=q)
        return queryset

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """새 태그 생성 또는 기존 태그 재사용 후 공고와 연결"""
        recruitment_id = self.kwargs["recruitment_id"]

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name: str = serializer.validated_data["name"]

        # 태그가 이미 존재하면 재사용, 없으면 새로 생성
        tag, _ = Tag.objects.get_or_create(name__iexact=name, defaults={"name": name})

        # 이미 공고에 연결되어 있으면 예외 처리
        if RecruitmentTag.objects.filter(recruitment_id=recruitment_id, tag=tag).exists():
            return Response(
                {"detail": "이미 이 공고에 연결된 태그입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 공고-태그 연결 생성
        RecruitmentTag.objects.create(recruitment_id=recruitment_id, tag=tag)

        return Response(
            self.get_serializer(tag).data,
            status=status.HTTP_201_CREATED,
        )
