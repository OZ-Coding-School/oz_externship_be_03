from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.recruitments.models import Tag
from apps.recruitments.serializers.tag import TagSerializer


class TagPagination(PageNumberPagination):
    """태그 목록 페이지네이션"""

    page_size: int = 5
    page_size_query_param: str = "page_size"  #  클라이언트가 페이지 크기 조절 가능


@extend_schema(
    tags=["RecruitmentTags"],
    parameters=[
        OpenApiParameter(
            name="recruitment_id",
            type=int,
            location=OpenApiParameter.PATH,
            description="공고 ID (URL 경로에서 자동 전달됨)",
            required=False,
        )
    ],
)
class RecruitmentTagListCreateView(generics.ListCreateAPIView[Tag]):
    """
    특정 공고의 태그 목록 조회 및 신규 태그 등록 API.

    - 검색(q) 파라미터로 이름 필터링 지원
    - 중복 태그 등록 시 400 에러 반환
    """

    serializer_class: type[TagSerializer] = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = TagPagination

    def get_queryset(self) -> Any:
        """검색어(q)가 없으면 전체, 있으면 필터링"""
        q = self.request.query_params.get("q", "").strip()
        queryset = Tag.objects.all().order_by("id")
        if q:
            queryset = queryset.filter(name__icontains=q)
        return queryset

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        """recruitment_id는 URL로만 받되, Tag에는 직접 저장하지 않음"""
        recruitment_id = self.kwargs.get("recruitment_id")
        if not recruitment_id:
            raise ValidationError({"detail": "URL에 recruitment_id가 누락되었습니다."})
        serializer.save()

    @extend_schema(
        summary="특정 공고의 태그 목록 조회",
        description="검색(q) 파라미터로 이름을 필터링할 수 있습니다. 없으면 전체 태그를 반환합니다.",
        responses={200: TagSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """태그 목록 조회"""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="신규 태그 등록",
        description="기존에 없는 새로운 태그를 등록합니다. 이미 존재하면 400 응답을 반환합니다.",
        request=TagSerializer,
        responses={
            201: TagSerializer,
            400: {"example": {"detail": "이미 존재하는 태그입니다."}},
        },
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """새로운 태그 등록"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name: str = serializer.validated_data["name"]
        if Tag.objects.filter(name__iexact=name).exists():
            return Response(
                {"detail": "이미 존재하는 태그입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
