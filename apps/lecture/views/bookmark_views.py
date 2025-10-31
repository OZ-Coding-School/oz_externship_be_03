from typing import TYPE_CHECKING, cast

from django.db.models import Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.exceptions import ValidationError
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
    serializer_class = LectureBookmarkListSerializer

    @extend_schema(
        tags=["Lectures"],
        summary="강의 북마크 목록 조회 API",
        responses={
            200: LectureBookmarkListSerializer(many=True),
            401: {"description": "인증이 필요합니다."},
        },
    )
    def get(self, request: Request) -> Response:
        user: User = cast(User, request.user)
        search: str = request.GET.get("search", "").strip()

        # 사용자의 북마크 목록 조회 (최신순 정렬)
        queryset: QuerySet[LectureBookmark] = (
            LectureBookmark.objects.filter(user=user).select_related("lecture").order_by("-created_at")
        )

        # 검색어가 있는 경우 강의명 또는 강사명으로 필터링
        if search:
            queryset = queryset.filter(Q(lecture__title__icontains=search) | Q(lecture__instructor__icontains=search))

        paginator = self.pagination_class()

        # 페이지네이션 적용
        # - 쿼리 파라미터 'page'가 없으면 자동으로 첫 페이지(page=1) 반환
        # - 잘못된 페이지 번호(문자열, 음수 등)는 첫 페이지로 처리
        # - PageNumberPagination.paginate_queryset()가 내부적으로 처리
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(page, many=True)
        paginated_response = paginator.get_paginated_response(serializer.data)

        return Response(
            {
                "detail": "북마크 강의 목록 조회가 완료되었습니다.",
                "data": paginated_response.data,
            }
        )

    @extend_schema(
        tags=["Lectures"],
        summary="강의 북마크 추가 API",
        request=LectureBookmarkCreateSerializer,
        responses={
            201: {"description": "북마크가 추가되었습니다."},
            400: {"description": "이미 북마크한 강의입니다."},
            401: {"description": "인증이 필요합니다."},
        },
    )
    def post(self, request: Request) -> Response:
        user: User = cast(User, request.user)
        serializer = LectureBookmarkCreateSerializer(data=request.data)

        if serializer.is_valid():
            try:
                serializer.save(user=user)
                return Response(
                    {"detail": "북마크가 추가되었습니다."},
                    status=status.HTTP_201_CREATED,
                )
            except ValidationError:
                return Response(
                    {"error": "이미 북마크한 강의입니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
            user: User = cast(User, request.user)
            bookmark = LectureBookmark.objects.get(user=user, lecture_id=lecture_id)
            bookmark.delete()
            return Response({"detail": "북마크가 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)
        except LectureBookmark.DoesNotExist:
            return Response({"error": "존재하지 않는 북마크입니다."}, status=status.HTTP_404_NOT_FOUND)
