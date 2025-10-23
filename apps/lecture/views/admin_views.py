from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.filters import LectureFilter
from apps.lecture.models import CrawledLecture
from apps.lecture.serializers import (
    AdminLectureDetailSerializer,
    AdminLectureListSerializer,
)


class AdminLectureListView(APIView):
    """어드민용 강의 목록 조회 API"""

    serializer_class = AdminLectureListSerializer
    permission_classes = [AllowAny]  # 기능 구현시 변경

    @extend_schema(
        operation_id="v1_admin_lecture_list",
        tags=["Lectures"],
        summary="어드민용 강의 목록 조회 API",
        responses={200: AdminLectureListSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        mock_data = {
            "count": 150,
            "next": "http://example.com/api/v1/admin/lectures/?page=2",
            "previous": None,
            "results": [
                {
                    "id": i,
                    "title": f"Django 완벽 가이드 {i}",
                    "instructor": "Meoyoug",
                    "thumbnail_img_url": "https://example.com/image.jpg",
                    "platform": "INFLEARN",
                    "url_link": "https://www.inflearn.com/course/django",
                    "categories": [
                        {"id": 1, "name": "백엔드"},
                        {"id": 5, "name": "Django"},
                    ],
                    "created_at": "2025-10-20 14:30:00",
                    "updated_at": "2025-10-22 09:15:00",
                }
                for i in range(1, 11)
            ],
        }

        return Response(mock_data, status=status.HTTP_200_OK)

        # TODO: 완성되면 spec용 api 제거후 주석 해제
        # queryset = CrawledLecture.objects.prefetch_related("lecture_categories__category").all()
        #
        # # 검색 기능
        # filterset = LectureFilter(request.query_params, queryset=queryset)
        # queryset = filterset.qs
        #
        # # 페이지네이션
        # paginator = LimitOffsetPagination()
        # page = paginator.paginate_queryset(queryset, request)
        # serializer = AdminLectureListSerializer(page, many=True)
        # return paginator.get_paginated_response(serializer.data)


class AdminLectureDetailView(APIView):
    """어드민용 강의 상세 조회 API"""

    serializer_class = AdminLectureDetailSerializer
    permission_classes = [AllowAny]  # 기능구현시 변경

    @extend_schema(
        operation_id="v1_admin_lecture_detail",
        tags=["Lectures"],
        summary="어드민용 강의 상세 조회 API",
        responses={200: AdminLectureDetailSerializer(many=True)},
    )
    def get(self, request: Request, lecture_id: int) -> Response:
        mock_data = {
            "id": lecture_id,
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Django 완벽 가이드",
            "instructor": "Meoyoug",
            "thumbnail_img_url": "https://example.com/image.jpg",
            "description": "Django를 처음부터 끝까지 완벽하게 배우는 강의입니다.",
            "difficulty": "HARD",
            "duration": 1200,
            "original_price": 100000,
            "discount_price": 50000,
            "platform": "INFLEARN",
            "url_link": "https://www.inflearn.com/course/django",
            "categories": [
                {"id": 1, "name": "백엔드"},
                {"id": 5, "name": "Django"},
            ],
            "created_at": "2025-10-20 14:30:00",
            "updated_at": "2025-10-22 09:15:00",
        }

        return Response(mock_data, status=status.HTTP_200_OK)

        # TODO: 위와같음
        # try:
        #     lecture = CrawledLecture.objects.prefetch_related("lecture_categories__category").get(pk=lecture_id)
        # except CrawledLecture.DoesNotExist:
        #     return Response({"detail": "lecture_not_found"}, status=status.HTTP_404_NOT_FOUND)
        #
        # serializer = AdminLectureDetailSerializer(lecture)
        # return Response(serializer.data, status=status.HTTP_200_OK)
