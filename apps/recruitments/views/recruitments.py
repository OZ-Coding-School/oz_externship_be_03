from typing import Any

from django.db.models import Count, QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.recruitments import (
    RecruitmentCreateUpdateSerializer,
    RecruitmentDetailSerializer,
    RecruitmentListSerializer,
    RecruitmentUpdateSerializer,
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


# 목록 + 생성
class RecruitmentListCreateAPIView(generics.GenericAPIView[Recruitment], ListModelMixin):
    """공고 목록 + 생성"""

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = RecruitmentListSerializer
    pagination_class = RecruitmentPagination

    def get_queryset(self) -> QuerySet[Recruitment]:
        """목록 필터/정렬"""
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
            return qs.order_by("-views_count")
        if ordering == "bookmarks":
            return qs.order_by("-bookmark_count")

        return qs.order_by("-created_at")

    @extend_schema(
        tags=["Recruitments"],
        summary="스터디 구인공고 목록 조회",
        parameters=[
            OpenApiParameter("keyword", required=False),
            OpenApiParameter("tag", required=False),
            OpenApiParameter("ordering", enum=VALID_ORDERING_PARAMS, required=False),
        ],
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """공고 목록"""
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        data = RecruitmentListSerializer(page, many=True, context={"request": request}).data
        response = self.get_paginated_response(data)

        # 추천 공고
        if request.user.is_authenticated and isinstance(request.user, User):
            rec = get_recommended_recruitments_for_user(request.user, limit=3)
            response.data["recommended_recruitments"] = RecruitmentListSerializer(
                rec, many=True, context={"request": request}
            ).data
        else:
            response.data["recommended_recruitments"] = []

        return response

    @extend_schema(
        tags=["Recruitments"],
        summary="스터디 구인 공고 생성",
        request={"multipart/form-data": RecruitmentCreateUpdateSerializer},
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """공고 생성"""
        serializer = RecruitmentCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not isinstance(request.user, User):
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        recruitment = create_recruitment(request.user, serializer.validated_data)
        data = RecruitmentDetailSerializer(recruitment, context={"request": request}).data

        return Response(data, status=status.HTTP_201_CREATED)


# 내가 작성한 공고
class RecruitmentUserListAPIView(generics.ListAPIView[Recruitment]):
    """내가 작성한 공고"""

    serializer_class = RecruitmentListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = RecruitmentPagination

    def get_queryset(self) -> QuerySet[Recruitment]:
        """내 공고 + 상태별 필터링"""
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
            return qs.order_by("-views_count")
        if ordering == "bookmarks":
            return qs.order_by("-bookmark_count")

        return qs.order_by("-created_at")


# 상세 / 수정 / 삭제
class RecruitmentDetailUpdateDeleteAPIView(generics.RetrieveUpdateDestroyAPIView[Recruitment]):
    """공고 상세 / 수정 / 삭제"""

    lookup_field = "uuid"
    lookup_url_kwarg = "recruitment_uuid"
    queryset = Recruitment.objects.annotate(bookmark_count=Count("bookmarks")).prefetch_related(
        "tags", "images", "attachments"
    )
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self) -> type[Serializer[Any]]:
        """요청 방식에 따라 Serializer 분기"""
        if self.request.method == "PATCH":
            return RecruitmentUpdateSerializer
        if self.request.method == "PUT":
            return RecruitmentCreateUpdateSerializer
        return RecruitmentDetailSerializer

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """상세 조회"""
        instance = self.get_object()
        increase_views(instance)
        data = RecruitmentDetailSerializer(instance, context={"request": request}).data
        return Response(data)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """공고 수정"""
        instance = self.get_object()
        partial = request.method == "PATCH"

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        updated = update_recruitment(instance, serializer.validated_data)
        data = RecruitmentDetailSerializer(updated, context={"request": request}).data

        return Response(data, status=status.HTTP_200_OK)


#  presigned-url API 추가
class RecruitmentPresignedURLAPIView(APIView):
    """파일 업로드용 presigned-url 생성"""

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response({"url": "presigned-url-sample", "fields": {}}, status=status.HTTP_200_OK)
