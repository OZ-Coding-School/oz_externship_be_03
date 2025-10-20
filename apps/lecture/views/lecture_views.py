from django.db.models import Q
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from apps.lecture.filters import LectureFilter

from apps.lecture.models import CrawledLecture, CrawledLectureReview, LectureSearchLog
from apps.lecture.serializers import (
    LectureListSerializer,
    LectureReviewSerializer,
)

@extend_schema(
    tags=["Lecture"],
    summary="강의 목록 조회 API",
    description="""
    강의 플랫폼의 강의 목록을 검색, 필터링, 정렬하여 조회합니다. 무한스크롤을 위한 페이지네이션을 지원합니다.
    """
)
class LectureListView(APIView):
    """
    강의 목록 조회 API

    - 검색: ?search=키워드&search_type=(all, title, instructor)
    - 카테고리 필터: ?category=카테고리명
    - 플랫폼 필터: ?platform=(udemy, inflearn)
    - 정렬: ?ordering=(-create_at, -price, price, rating, -rating)
    """

    def get(self, request: Request) -> Response:
        queryset = CrawledLecture.objects.all()

        # 서치 타입 validation
        search_type = request.query_params.get("search_type", "all")
        valid_search_types = ["all", "title", "instructor"]
        if search_type not in valid_search_types:
            return Response({"detail": "invalid_search_type"}, status=status.HTTP_400_BAD_REQUEST)

        # 필터
        filterset =  LectureFilter(request.query_params, queryset=queryset, request=request)
        queryset = filterset.qs

        # 검색 로그 저장
        search_keyword = request.query_params.get("search")
        if search_keyword and request.user.is_authenticated:
            LectureSearchLog.objects.create(user=request.user, keyword=search_keyword)

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = LectureListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class LectureReviewListView(APIView):
    """
    강의 리뷰 조회
    최근 리뷰 최개 4개 반환
    """

    def get(self, request: Request, lecture_id: int) -> Response:
        try:
            lecture = CrawledLecture.objects.get(pk=lecture_id)
        except CrawledLecture.DoesNotExist:
            return Response({"detail": "lecture_not_found"}, status=status.HTTP_404_NOT_FOUND)

        reviews = CrawledLectureReview.objects.filter(
            lecture=lecture,
        ).order_by(
            "-created_at"
        )[:4]

        serializer = LectureReviewSerializer(reviews, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
