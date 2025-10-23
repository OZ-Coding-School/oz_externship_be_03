from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.views import APIView

from apps.lecture.serializers import (
    AdminLectureListSerializer,
    AdminLectureDetailSerializer,
)


class AdminLectureListView(APIView):
    """어드민용 강의 목록 조회 API"""

    serializer_class = AdminLectureListSerializer
    permission_classes = [AllowAny] # 기능 구현시 변경

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


class AdminLectureDetailView(APIView):
    """어드민용 강의 상세 조회 API"""

    serializer_class = AdminLectureDetailSerializer
    permission_classes = [AllowAny] # 기능구현시 변경

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
