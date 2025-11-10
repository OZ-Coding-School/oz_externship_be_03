from typing import Any, Optional

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import generics, parsers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.admin_serializers import (
    AdminRecruitmentDetailSerializer,
    AdminRecruitmentListSerializer,
)


class AdminRecruitmentPagination(PageNumberPagination):
    # 관리자 공고 목록 페이지네이션
    page_size = 10
    page_size_query_param = "page_size"

    def get_paginated_response(self, data: list[Any]) -> Response:
        total = Recruitment.objects.count()
        open_count = Recruitment.objects.filter(is_closed=False).count()
        closed_count = Recruitment.objects.filter(is_closed=True).count()

        # 페이지네이션이 비활성화된 경우(테스트용)
        if not hasattr(self, "page") or self.page is None or not hasattr(self.page, "paginator"):
            return Response(
                {
                    "results": data,
                    "count": {"total": total, "open": open_count, "closed": closed_count},
                    "page": None,
                    "page_size": None,
                }
            )

        return Response(
            {
                "results": data,
                "page": self.page.number,
                "page_size": self.page.paginator.per_page,
                "count": {"total": total, "open": open_count, "closed": closed_count},
            }
        )


class AdminRecruitmentListAPIView(generics.ListAPIView[Recruitment]):
    # 관리자 공고 목록 조회
    serializer_class = AdminRecruitmentListSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminRecruitmentPagination

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 목록 조회",
        responses={200: AdminRecruitmentListSerializer(many=True)},
    )
    def get_queryset(self) -> QuerySet[Recruitment]:
        qs = Recruitment.objects.all().prefetch_related("tags")

        title = self.request.query_params.get("title")
        status_param = self.request.query_params.get("status")
        is_closed_param = self.request.query_params.get("is_closed")
        tag_names = self.request.query_params.getlist("tags")

        if title:
            qs = qs.filter(title__icontains=title)

        # 상태와 is_closed=true/false 둘 다 지원
        if status_param in ("open", "closed"):
            qs = qs.filter(is_closed=(status_param == "closed"))
        elif is_closed_param in ("true", "false", "True", "False"):
            qs = qs.filter(is_closed=(is_closed_param.lower() == "true"))

        if tag_names:
            qs = qs.filter(tags__name__in=tag_names).distinct()

        ordering = self.request.query_params.get("ordering", "-created_at")
        return qs.order_by(ordering)


class AdminRecruitmentDetailAPIView(APIView):
    # 관리자 공고 상세 조회 및 삭제
    permission_classes = [IsAdminUser]
    parser_classes = [parsers.JSONParser]

    def get_object(self, recruitment_id: int) -> Optional[Recruitment]:
        return (
            Recruitment.objects.prefetch_related("tags", "attachments", "applications")
            .filter(id=recruitment_id)
            .first()
        )

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 상세 조회",
        responses={200: AdminRecruitmentDetailSerializer},
    )
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_id)
        if not recruitment:
            # 존재하지 않을 경우 404
            return Response({"detail": "조회하려는 공고가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminRecruitmentDetailSerializer(recruitment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 삭제",
        responses={
            204: None,
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
            404: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def delete(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_id)
        if not recruitment:
            return Response({"detail": "삭제하려는 공고를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        recruitment.delete()
        # 테스트 커버리지용 명시적 반환
        return Response({"detail": "삭제 완료"}, status=status.HTTP_204_NO_CONTENT)
