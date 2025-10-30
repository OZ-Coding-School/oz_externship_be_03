from typing import TYPE_CHECKING, List, Optional, cast

from django.db.models import Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import LectureBookmark
from apps.lecture.serializers.bookmark_serializers import (
    LectureBookmarkCreateSerializer,
    LectureBookmarkListSerializer,
)

if TYPE_CHECKING:
    from apps.users.models import User
else:
    from django.contrib.auth import get_user_model

    User = get_user_model()


class BookmarkPagination(PageNumberPagination):
    """북마크 목록 조회용 커스텀 페이지네이션"""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class LectureBookmarkListCreateView(APIView):
    """
    로그인 유저 북마크 목록 조회 및 북마크 추가 API
    GET: 목록 조회
    POST: 북마크 추가
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.JSONParser]
    pagination_class = BookmarkPagination

    @extend_schema(
        tags=["Lectures"],
        summary="강의 북마크 목록 조회 API",
        responses={
            200: LectureBookmarkListSerializer(many=True),
            400: {"description": "잘못된 요청"},
            401: {"description": "인증이 필요합니다."},
        },
    )
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        queryset: QuerySet[LectureBookmark] = (
            LectureBookmark.objects.filter(user=user).select_related("lecture").order_by("-created_at")
        )

        search = request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(Q(lecture__title__icontains=search) | Q(lecture__instructor__icontains=search))

        paginator = self.pagination_class()
        page: Optional[List[LectureBookmark]] = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = LectureBookmarkListSerializer(page, many=True)
            response_data = paginator.get_paginated_response(serializer.data)
            return Response(
                {"detail": "북마크 강의 목록 조회가 완료되었습니다.", "data": response_data.data},
                status=status.HTTP_200_OK,
            )

        serializer = LectureBookmarkListSerializer(queryset, many=True)
        return Response(
            {
                "detail": "북마크 강의 목록 조회가 완료되었습니다.",
                "data": {"count": queryset.count(), "next": None, "previous": None, "results": serializer.data},
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Lectures"],
        summary="강의 북마크 추가 API",
        request=LectureBookmarkCreateSerializer,
        responses={
            201: {"description": "북마크가 추가되었습니다."},
            400: {"description": "잘못된 요청 또는 중복 북마크"},
            401: {"description": "인증이 필요합니다."},
            404: {"description": "존재하지 않는 강의입니다."},
        },
    )
    def post(self, request: Request) -> Response:
        serializer = LectureBookmarkCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = cast(User, request.user)
            serializer.save(user=user)
            return Response({"detail": "북마크가 추가되었습니다."}, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            return Response(
                {"error": "북마크 생성 중 알 수 없는 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LectureBookmarkDeleteView(APIView):
    """북마크 삭제 API"""

    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["Lectures"],
        summary="강의 북마크 삭제 API",
        responses={
            204: {"description": "북마크가 삭제되었습니다."},
            401: {"description": "인증이 필요합니다."},
            404: {"description": "존재하지 않는 북마크입니다."},
        },
    )
    def delete(self, request: Request, lecture_id: int) -> Response:
        try:
            user = cast(User, request.user)

            bookmark = LectureBookmark.objects.get(user=user, lecture_id=lecture_id)
            bookmark.delete()
            return Response({"detail": "북마크가 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)
        except LectureBookmark.DoesNotExist:
            return Response({"error": "존재하지 않는 북마크입니다."}, status=status.HTTP_404_NOT_FOUND)
