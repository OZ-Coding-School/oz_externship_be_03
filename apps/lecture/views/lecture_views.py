from django.db.models import Prefetch, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.filters import LectureFilter
from apps.lecture.models import (
    CrawledLecture,
    CrawledLectureReview,
    LectureBookmark,
    LectureSearchLog,
)
from apps.lecture.serializers import (
    LectureListSerializer,
    LectureReviewSerializer,
)


class LectureListView(APIView):
    """강의 플랫폼(Udemy, Inflearn)의 강의 목록을 검색, 필터링, 정렬하여 조회하는 API입니다."""

    serializer_class = LectureListSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="v1_lecture_list",
        tags=["Lectures"],
        summary="강의 목록 조회 API",
        responses={200: LectureListSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        mock_data = {
            "count": 150,
            "next": "http://example.com/api/v1/lectures/?page=2",
            "previous": None,
            "results": [
                {
                    "id": i,
                    "uuid": "550e8400-e29b-41d4-a716-446655440000",
                    "title": f"Django 완벽 가이드 {i}",
                    "instructor": "Meoyoug",
                    "thumbnail_img_url": "https://example.com/image.jpg",
                    "categories": [
                        {"id": 1, "name": "백엔드"},
                        {"id": 5, "name": "Django"},
                    ],
                    "difficulty": "HARD",
                    "original_price": 100000,
                    "discount_price": 50000,
                    "platform": "inflearn",
                    "average_rating": 4.85,
                    "url_link": "https://www.inflearn.com/course/%EC%8B%A4%EC%A0%84-django-%EC%9E%85%EB%AC%B8",
                    "is_bookmarked": i % 2 == 0,
                }
                for i in range(1, 11)
            ],
        }

        return Response(mock_data, status=status.HTTP_200_OK)

    # TODO: 완성되면 spec용 api 제거후 주석 해제
    # def get(self, request: Request) -> Response:
    #     queryset = CrawledLecture.objects.prefetch_related("lecture_categories__category").all()
    #
    #     if request.user.is_authenticated:
    #         queryset = queryset.prefetch_related(
    #             Prefetch(
    #                 "bookmarks", queryset=LectureBookmark.objects.filter(user=request.user), to_attr="user_bookmarks"
    #             )
    #         )
    #
    #     # 필터
    #     filterset = LectureFilter(request.query_params, queryset=queryset, request=request)
    #     queryset = filterset.qs
    #
    #     # 검색 로그 저장
    #     search_keyword = request.query_params.get("search")
    #     if search_keyword and request.user.is_authenticated:
    #         LectureSearchLog.objects.create(user=request.user, keyword=search_keyword)
    #
    #     paginator = PageNumberPagination()
    #     page = paginator.paginate_queryset(queryset, request)
    #     serializer = LectureListSerializer(page, many=True, context={"request": request})
    #     return paginator.get_paginated_response(serializer.data)


class LectureReviewListView(APIView):
    """특정 강의의 최근 리뷰를 최대 4개까지 조회합니다."""

    serializer_class = LectureReviewSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="v1_lecture_review_list",
        tags=["Lectures"],
        summary="강의 리뷰 조회 API",
        responses={200: LectureReviewSerializer(many=True)},
    )
    def get(self, request: Request, uuid: str) -> Response:
        mock_data = {
            "reviews": [
                {
                    "id": i,
                    "rating": "5_OUT_OF_5_STARS",
                    "content": f"정말 유익한 강의였습니다. {i}번이나 다시봤어요",
                    "created_at": "2025-10-10 14:30:00",
                }
                for i in range(1, 5)
            ]
        }

        return Response(mock_data, status=status.HTTP_200_OK)

        # TODO: 위와동일

        # try:
        #     lecture = CrawledLecture.objects.get(pk=lecture_uuid)
        # except CrawledLecture.DoesNotExist:
        #     return Response({"detail": "lecture_not_found"}, status=status.HTTP_404_NOT_FOUND)
        #
        # reviews = CrawledLectureReview.objects.filter(
        #     lecture=lecture,
        # ).order_by(
        #     "-created_at"
        # )[:4]
        #
        # serializer = LectureReviewSerializer(reviews, many=True)
        # return Response(serializer.data, status=status.HTTP_200_OK)
