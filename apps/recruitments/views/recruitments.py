from typing import Any, Type

from django.contrib.auth.models import AnonymousUser
from django.db.models import Count, QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

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

VALID_ORDERING_PARAMS = ("latest", "views", "bookmarks")


# List & Create API
class RecruitmentListCreateAPIView(generics.GenericAPIView[Recruitment], ListModelMixin):
    """스터디 구인공고 목록 조회 및 작성"""

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class: Type[RecruitmentListSerializer] = RecruitmentListSerializer
    pagination_class = RecruitmentPagination

    def get_queryset(self) -> QuerySet[Recruitment]:
        qs = (
            Recruitment.objects.filter(is_closed=False)
            .annotate(bookmark_count=Count("bookmarks"))
            .prefetch_related("tags", "images", "attachments")
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

    @extend_schema(
        tags=["Recruitments"],
        summary="스터디 구인 공고 목록 조회",
        description="로그인 사용자는 공고 목록 조회 가능 (검색/태그 필터/정렬)",
        parameters=[
            OpenApiParameter("keyword", OpenApiTypes.STR, required=False, description="공고 제목 검색"),
            OpenApiParameter("tag", OpenApiTypes.STR, required=False, description="태그 필터링"),
            OpenApiParameter("ordering", enum=VALID_ORDERING_PARAMS, required=False, description="정렬 기준"),
        ],
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        serializer = self.serializer_class(page, many=True, context={"request": request})
        response = self.get_paginated_response(serializer.data)

        if request.user.is_authenticated:
            # User 타입만 안전하게 전달
            if isinstance(request.user, User):
                user_obj: User = request.user
                recommended_qs = get_recommended_recruitments_for_user(user_obj, limit=3)
            else:
                recommended_qs = Recruitment.objects.none()

            recommended_serializer = RecruitmentListSerializer(recommended_qs, many=True, context={"request": request})
            response.data["recommended_recruitments"] = recommended_serializer.data
        else:
            response.data["recommended_recruitments"] = []

        return response

    @extend_schema(
        tags=["Recruitments"],
        summary="스터디 구인 공고 작성",
        description=(
            "로그인한 사용자는 공고 등록 가능\n"
            "- content: 마크다운 형식\n"
            "- 이미지 최대 5개, 첨부파일 최대 3개\n"
            "- tags 값 없으면 ['undefined'] 처리\n"
            "- estimated_fee 값 없으면 백엔드에서 계산"
        ),
        request={"multipart/form-data": RecruitmentCreateUpdateSerializer},
        responses={
            201: OpenApiResponse(response=RecruitmentDetailSerializer, description="공고 등록 성공"),
            400: OpenApiResponse(description="잘못된 요청"),
            401: OpenApiResponse(description="인증되지 않은 사용자"),
        },
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = RecruitmentCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get("estimated_fee") is None:
            serializer.validated_data["estimated_fee"] = 10000  # 기본값

        if not serializer.validated_data.get("tags"):
            serializer.validated_data["tags"] = ["undefined"]

        # User 타입 체크 후 create_recruitment 호출
        if isinstance(request.user, User):
            user_obj: User = request.user
            recruitment = create_recruitment(user_obj, serializer.validated_data)
        else:
            return Response({"detail": "인증되지 않은 사용자"}, status=401)

        detail_serializer = RecruitmentDetailSerializer(recruitment, context={"request": request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


# User-specific list API
class RecruitmentUserListAPIView(generics.ListAPIView[Recruitment]):
    """사용자별 공고 목록 조회"""

    serializer_class = RecruitmentListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = RecruitmentPagination

    @extend_schema(
        tags=["Recruitments"],
        summary="내가 작성한 공고 목록 조회",
        parameters=[
            OpenApiParameter("status", enum=["open", "closed"], required=False, description="공고 상태 필터"),
            OpenApiParameter("ordering", enum=VALID_ORDERING_PARAMS, required=False, description="정렬 기준"),
        ],
    )
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


# Detail / Update / Delete API
class RecruitmentDetailUpdateDeleteAPIView(generics.RetrieveUpdateDestroyAPIView[Recruitment]):
    """공고 상세 조회 / 수정 / 삭제"""

    lookup_field = "uuid"
    lookup_url_kwarg = "recruitment_uuid"
    queryset = (
        Recruitment.objects.all()
        .annotate(bookmark_count=Count("bookmarks"))
        .prefetch_related("tags", "images", "attachments")
    )
    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(tags=["Recruitments"], summary="상세/수정/삭제 API")
    def get_serializer_class(self) -> Type[Serializer[Any]]:
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
        """PUT/PATCH 시 create/update serializer 검증 후 detail serializer로 응답"""
        instance = self.get_object()
        serializer = RecruitmentCreateUpdateSerializer(instance, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        updated_instance = update_recruitment(instance, serializer.validated_data)

        response_serializer = RecruitmentDetailSerializer(updated_instance, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)
