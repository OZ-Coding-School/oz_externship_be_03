from typing import Any, cast

from django.contrib.auth.models import AbstractUser
from django.db.models import Count, QuerySet
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, Serializer

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.recruitments import (
    RecruitmentCreateUpdateSerializer,
    RecruitmentDetailSerializer,
    RecruitmentListSerializer,
)
from apps.recruitments.services.pagination import RecruitmentPagination
from apps.recruitments.services.recruitments import (
    create_recruitment,
    get_recommended_recruitments_for_user,
    increase_views,
    update_recruitment,
)
from apps.users.models import User


@extend_schema(
    tags=["recruitments"],
    summary="스터디 구인 공고 작성 및 목록 조회",
    description=(
        "로그인한 사용자는 새로운 스터디 구인 공고를 등록할 수 있습니다.\n\n"
        "- 마크다운 형식 본문(content)\n"
        "- 이미지 최대 5개 (5MB 이하)\n"
        "- 첨부파일 최대 3개 (5MB 이하)\n"
        "- 공고당 최대 5개의 사용자 정의 태그 등록 가능"
    ),
    request={"multipart/form-data": RecruitmentCreateUpdateSerializer},
    responses={
        200: OpenApiResponse(response=RecruitmentListSerializer, description="스터디 구인 공고 목록 조회 성공"),
        201: OpenApiResponse(response=RecruitmentDetailSerializer, description="스터디 구인 공고 등록 성공"),
        400: OpenApiResponse(description="유효하지 않은 요청 데이터"),
        401: OpenApiResponse(description="인증되지 않은 사용자"),
    },
)
class RecruitmentListCreateAPIView(generics.GenericAPIView):  # type: ignore[type-arg]
    """REQ-RECM-001, REQ-RECM-003 — 스터디 구인공고 목록 조회 및 생성"""

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class: type[RecruitmentListSerializer] = RecruitmentListSerializer
    pagination_class = RecruitmentPagination

    def get_queryset(self) -> QuerySet[Recruitment]:
        qs = (
            Recruitment.objects.filter(is_closed=False)
            .annotate(bookmark_count=Count("bookmarks"))
            .prefetch_related("tags", "images", "attachments")
            .order_by("-created_at")
        )
        keyword = self.request.query_params.get("keyword")
        tag = self.request.query_params.get("tag")
        ordering = self.request.query_params.get("ordering", "latest")

        if keyword:
            qs = qs.filter(title__icontains=keyword)
        if tag:
            qs = qs.filter(tags__name__icontains=tag)

        if ordering == "views":
            qs = qs.order_by("-views_count")
        elif ordering == "bookmarks":
            qs = qs.order_by("-bookmark_count")
        else:
            qs = qs.order_by("-created_at")

        return qs

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        serializer = RecruitmentListSerializer(page, many=True, context={"request": request})
        paginated = self.get_paginated_response(serializer.data).data

        if request.user.is_authenticated:
            user = cast(User, request.user)  # type: ignore[redundant-cast]
            recommended_qs = get_recommended_recruitments_for_user(user, limit=3)
            recommended_serializer = RecruitmentListSerializer(recommended_qs, many=True, context={"request": request})
            paginated["recommended_recruitments"] = recommended_serializer.data
        else:
            paginated["recommended_recruitments"] = []

        return Response(paginated)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = RecruitmentCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = cast(User, request.user)
        recruitment = create_recruitment(user, serializer.validated_data)
        detail_serializer = RecruitmentDetailSerializer(recruitment, context={"request": request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["recruitments"], summary="내가 작성한 스터디 구인 공고 목록 조회")
class RecruitmentUserListAPIView(generics.ListAPIView):  # type: ignore[type-arg]
    """REQ-RECM-005 — 사용자별 스터디 구인 공고 목록 조회"""

    serializer_class = RecruitmentListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = RecruitmentPagination

    def get_queryset(self) -> QuerySet[Recruitment]:
        qs = (
            Recruitment.objects.filter(author_id=self.request.user.id)
            .annotate(bookmark_count=Count("bookmarks"))
            .prefetch_related("tags", "images", "study_group__lectures")
        )

        status_param = self.request.query_params.get("status")
        ordering = self.request.query_params.get("ordering", "latest")

        if status_param == "open":
            qs = qs.filter(is_closed=False)
        elif status_param == "closed":
            qs = qs.filter(is_closed=True)

        if ordering == "views":
            qs = qs.order_by("-views_count")
        elif ordering == "bookmarks":
            qs = qs.order_by("-bookmark_count")
        else:
            qs = qs.order_by("-created_at")

        return qs


@extend_schema(tags=["recruitments"], summary="스터디 구인 공고 상세 조회 / 수정 / 삭제")
class RecruitmentDetailUpdateDeleteAPIView(generics.RetrieveUpdateDestroyAPIView):  # type: ignore[type-arg]
    """REQ-RECM-006, 007, 009 — 스터디 구인 공고 상세, 수정, 삭제"""

    lookup_field = "uuid"
    lookup_url_kwarg = "recruitment_uuid"
    queryset = (
        Recruitment.objects.all()
        .annotate(bookmark_count=Count("bookmarks"))
        .prefetch_related("tags", "images", "attachments")
    )
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self) -> type[Serializer[Any]]:
        if self.request.method in ("PUT", "PATCH"):
            return RecruitmentCreateUpdateSerializer
        elif self.request.method == "GET":
            return RecruitmentDetailSerializer
        return RecruitmentDetailSerializer

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        increase_views(instance)
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """PUT/PATCH 시에는 create/update serializer로 검증 → detail serializer로 응답"""
        instance = self.get_object()
        serializer = RecruitmentCreateUpdateSerializer(instance, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        updated_instance = update_recruitment(instance, serializer.validated_data)

        response_serializer = RecruitmentDetailSerializer(updated_instance, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)
