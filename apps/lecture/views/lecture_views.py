from django.db.models import Q
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import CrawledLecture, CrawledLectureReview, LectureSearchLog
from apps.lecture.serializers import (
    LectureDetailSerializer,
    LectureListSerializer,
    LectureReviewSerializer,
)


class LectureListView(APIView):
    """
    강의 목록 조회
    - 검색: ?search=키워드
    - 카테고리 필터: ?category=카테고리명
    - 정렬: ?ordering=-create_at (최신순,기본값)
    """

    def get(self, request: Request) -> Response:
        queryset = CrawledLecture.objects.all()

        # 검색 기능
        search_keyword = request.query_params.get("search")
        if search_keyword:
            queryset = queryset.filter(Q(title__icontains=search_keyword) | Q(description__icontains=search_keyword))

            # 저장
            if request.user.is_authenticated:
                LectureSearchLog.objects.create(user=request.user, keyword=search_keyword)

        # 필터링
        category_name = request.query_params.get("category")
        if category_name:
            queryset = queryset.filter(lecture_categories__category__name=category_name).distinct()

        # 정렬
        ordering = request.query_params.get("ordering", "-create_at")

        ordering_map = {
            "-created_at": "-created_at",  # 최신순 (기본)
            "created_at": "created_at",  # 오래된 순
            "price": "original_price",  # 가격 낮은 순
            "-price": "-original_price",  # 가격 높은 순
            "rating": "average_rating",  # 평점 낮은 순
            "-rating": "-average_rating",  # 평점 높은 순
        }

        order_field = ordering_map.get(ordering, "-created_at")
        queryset = queryset.order_by(order_field)

        serializer = LectureListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LectureDetailView(APIView):
    """강의 상세 조회"""

    def get(self, request: Request, pk: int) -> Response:
        try:
            lecture = CrawledLecture.objects.get(pk=pk)
        except CrawledLecture.DoesNotExist:
            return Response({"detail": "lecture_not_found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = LectureDetailSerializer(lecture)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
