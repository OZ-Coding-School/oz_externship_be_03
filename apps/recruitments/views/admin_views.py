from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import parsers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.admin_serializers import (
    AdminRecruitmentDetailSerializer,
    AdminRecruitmentSerializer,
)


# 관리자용 공고 목록 페이지네이션 설정
class RecruitmentAdminPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class AdminRecruitmentListAPIView(APIView):
    # 관리자용 스터디 구인공고 목록 조회
    permission_classes = [IsAdminUser]
    serializer_class = AdminRecruitmentSerializer
    pagination_class = RecruitmentAdminPagination

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 목록 조회",
        description="관리자가 등록된 스터디 구인공고를 조회합니다. 태그(tag), 마감 여부(is_closed) 필터 및 페이지네이션(page, page_size)을 지원합니다.",
        parameters=[
            OpenApiParameter("tag", str, description="태그명 필터"),
            OpenApiParameter("is_closed", bool, description="마감 여부 필터 (true / false)"),
            OpenApiParameter("page", int, description="페이지 번호 (기본값 1)"),
            OpenApiParameter("page_size", int, description="페이지당 항목 수 (기본값 10)"),
        ],
        responses={200: AdminRecruitmentSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 기본 쿼리셋 (최신순 정렬 추가)
        qs = (
            Recruitment.objects.select_related("author", "study_group").prefetch_related("tags").order_by("-created_at")
        )

        # 태그명 필터
        tag = request.query_params.get("tag")
        if tag:
            qs = qs.filter(tags__name__icontains=tag)

        # 마감 여부 필터
        is_closed = request.query_params.get("is_closed")
        if is_closed:
            v = is_closed.lower()
            if v in ("true", "1"):
                qs = qs.filter(is_closed=True)
            elif v in ("false", "0"):
                qs = qs.filter(is_closed=False)

        # 페이지네이션 적용
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminRecruitmentDetailAPIView(APIView):
    # 관리자용 스터디 구인공고 상세 조회 및 삭제
    permission_classes = [IsAdminUser]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]
    serializer_class = AdminRecruitmentDetailSerializer

    # 단일 공고 조회
    def get_object(self, recruitment_id: int) -> Recruitment | None:
        return (
            Recruitment.objects.select_related("author", "study_group")
            .prefetch_related("tags")
            .filter(id=recruitment_id)
            .first()
        )

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 상세 조회",
        description="특정 스터디 구인공고의 상세 정보를 조회합니다.",
        responses={
            200: AdminRecruitmentDetailSerializer,
            404: {"type": "object", "properties": {"message": {"type": "string"}}},
        },
    )
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        # 공고 상세 조회
        recruitment = self.get_object(recruitment_id)
        if not recruitment:
            return Response({"message": "해당 공고를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(recruitment)
        return Response(serializer.data)

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 삭제",
        description="특정 스터디 구인공고를 삭제합니다.",
        responses={
            204: None,
            404: {"type": "object", "properties": {"message": {"type": "string"}}},
        },
    )
    def delete(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        # 공고 삭제
        recruitment = self.get_object(recruitment_id)
        if not recruitment:
            return Response({"message": "해당 공고를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        recruitment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
