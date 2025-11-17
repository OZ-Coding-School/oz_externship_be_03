from typing import Any, Optional
from uuid import UUID

from django.db.models import Count, QuerySet, TextChoices
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, parsers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.admin_recruitment_serializers import (
    AdminRecruitmentDetailSerializer,
    AdminRecruitmentListSerializer,
)


class AdminRecruitmentPagination(PageNumberPagination):
    """관리자 공고 목록 페이지네이션"""

    page_size = 10
    page_size_query_param = "page_size"


class AdminRecruitmentListAPIView(generics.ListAPIView[Recruitment]):
    """관리자 공고 목록 조회"""

    serializer_class = AdminRecruitmentListSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminRecruitmentPagination
    valid_status_params = ("open", "closed")

    class OrderingChoices(TextChoices):
        LATEST = "-created_at", "latest"
        OLDEST = "created_at", "oldest"
        MOST_BOOKMARKS = "-bookmark_count", "most_bookmarks"
        MOST_VIEWS = "-views_count", "most_views"

    @extend_schema(
        tags=["Admin"],
        summary="관리자용 스터디 구인공고 목록 조회",
        parameters=[
            OpenApiParameter(
                name="keyword",
                type=OpenApiTypes.STR,
                required=False,
                description="공고 제목을 기준으로 검색하기 위한 파라미터입니다.",
            ),
            OpenApiParameter(
                name="tag",
                type=OpenApiTypes.STR,
                required=False,
                many=True,
                description="공고 태그를 기준으로 필터링 하기 위한 파라미터입니다.",
            ),
            OpenApiParameter(
                name="status",
                enum=valid_status_params,
                required=False,
                description="공고를 오픈, 마감 여부 상태에 따라 필터링 하기 위한 파라미터입니다.",
            ),
            OpenApiParameter(
                name="ordering",
                enum=[OrderingChoices.labels],
                required=False,
                description="공고 목록을 기준에 따라 정렬하기 위한 파라미터입니다. (기본값은 최신순)",
            ),
        ],
        responses={200: AdminRecruitmentListSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Recruitment]:
        qs = Recruitment.objects.prefetch_related("tags").annotate(bookmark_count=Count("bookmarks"))
        keyword = self.request.query_params.get("keyword")
        status_param = self.request.query_params.get("status", "")
        tags = self.request.query_params.getlist("tag", [])
        ordering_param = self.request.query_params.get("ordering", self.OrderingChoices.LATEST)
        ordering = getattr(self.OrderingChoices, ordering_param.upper(), self.OrderingChoices.LATEST)

        if keyword:
            qs = qs.filter(title__icontains=keyword)

        if status_param in self.valid_status_params:
            qs = qs.filter(is_closed=(status_param == self.valid_status_params[1]))

        if tags:
            qs = qs.filter(tags__name__in=tags).distinct()

        if ordering:
            qs = qs.order_by(ordering)

        return qs


class AdminRecruitmentDetailAPIView(APIView):
    """관리자 공고 상세 조회 및 삭제"""

    permission_classes = [IsAdminUser]
    parser_classes = [parsers.JSONParser]

    def get_object(self, recruitment_uuid: UUID) -> Optional[Recruitment]:
        return (
            Recruitment.objects.prefetch_related("tags", "attachments", "applications")
            .annotate(bookmark_count=Count("bookmarks"))
            .filter(uuid=recruitment_uuid)
            .first()
        )

    @extend_schema(
        tags=["Admin"],
        summary="관리자용 스터디 구인공고 상세 조회",
        responses={200: AdminRecruitmentDetailSerializer},
    )
    def get(self, request: Request, recruitment_uuid: UUID, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_uuid)
        if not recruitment:
            return Response({"detail": "조회하려는 공고가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminRecruitmentDetailSerializer(recruitment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Admin"],
        summary="관리자용 스터디 구인공고 삭제",
        responses={
            204: None,
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
            404: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def delete(self, request: Request, recruitment_uuid: UUID, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_uuid)
        if not recruitment:
            return Response({"detail": "삭제하려는 공고를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        recruitment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
