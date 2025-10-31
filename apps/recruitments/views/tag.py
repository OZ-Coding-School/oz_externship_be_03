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

from apps.recruitments.models import RecruitmentTag, Tag  # 중간 테이블 추가 import
from apps.recruitments.serializers.tag import TagSerializer


class TagPagination(PageNumberPagination):
    """태그 목록 페이지네이션"""

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
            description="공고 ID (URL 경로에서 자동 전달됨)",
            required=True,
        ),
        OpenApiParameter(
            name="q",
            type=str,
            location=OpenApiParameter.QUERY,
            description="태그명 검색 키워드 (부분 일치)",
            required=False,
        ),
    ],
)
class RecruitmentTagListCreateView(generics.ListCreateAPIView[Tag]):
    """
    특정 공고의 태그 목록 조회 및 신규 태그 등록 API.
    - 검색(q) 파라미터로 이름 필터링 지원
    - 중복 태그 등록 시 400 에러 반환
    """

    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = TagPagination

    def get_queryset(self) -> Any:
        """특정 공고에 연결된 태그만 필터링"""
        recruitment_id = self.kwargs.get("recruitment_id")
        if recruitment_id is None:
            raise ValidationError({"detail": "recruitment_id가 필요합니다."})

        q = self.request.query_params.get("q", "").strip()

        queryset = Tag.objects.filter(recruitment_tags__recruitment_id=recruitment_id).order_by("id")

        if q:
            queryset = queryset.filter(name__icontains=q)

        return queryset

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        """Tag를 생성하고 RecruitmentTag를 통해 공고와 연결"""
        recruitment_id = self.kwargs.get("recruitment_id")
        if not recruitment_id:
            raise ValidationError({"detail": "URL에 recruitment_id가 누락되었습니다."})

        # 태그 생성
        tag = serializer.save()

        #  이미 연결된 관계가 있는지 확인
        if RecruitmentTag.objects.filter(recruitment_id=recruitment_id, tag=tag).exists():
            raise ValidationError({"detail": "이미 이 공고에 연결된 태그입니다."})

        #  공고-태그 연결 생성
        RecruitmentTag.objects.create(recruitment_id=recruitment_id, tag=tag)

    @extend_schema(
        summary="특정 공고의 태그 목록 조회",
        description=(
            "특정 공고(recruitment_id)에 연결된 태그 목록을 반환합니다.\n"
            "검색어(q)를 전달하면 이름에 해당 문자열이 포함된 태그만 필터링합니다."
        ),
        responses={200: TagSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """특정 공고의 태그 목록 조회"""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="신규 태그 등록",
        description=(
            "새로운 태그를 등록합니다. 이미 존재하는 태그명을 등록할 경우 400 에러를 반환합니다.\n"
            "공고(recruitment_id)는 URL 경로를 통해 지정됩니다."
        ),
        request=TagSerializer,
        responses={
            201: TagSerializer,
            400: {"example": {"detail": "이미 존재하는 태그입니다."}},
        },
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """신규 태그 등록"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name: str = serializer.validated_data["name"]

        if Tag.objects.filter(name__iexact=name).exists():
            raise ValidationError({"detail": "이미 존재하는 태그입니다."})

        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
