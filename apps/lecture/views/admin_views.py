from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAdminUser
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
    permission_classes = [IsAdminUser]

    @extend_schema(
        operation_id="v1_admin_lecture_list",
        tags=["Lectures"],
        summary="어드민용 강의 목록 조회 API",
        responses={200: AdminLectureListSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        queryset = CrawledLecture.objects.prefetch_related("categories").all()

        # 검색 기능
        filterset = LectureFilter(request.query_params, queryset=queryset)
        queryset = filterset.qs

        # 페이지네이션
        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AdminLectureListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminLectureDetailView(APIView):
    """어드민용 강의 상세 조회 API"""

    serializer_class = AdminLectureDetailSerializer
    permission_classes = [IsAdminUser]

    @extend_schema(
        operation_id="v1_admin_lecture_detail",
        tags=["Lectures"],
        summary="어드민용 강의 상세 조회 API",
        responses={200: AdminLectureDetailSerializer(many=True)},
    )
    def get(self, request: Request, lecture_id: int) -> Response:
        try:
            lecture = CrawledLecture.objects.prefetch_related("categories").get(pk=lecture_id)
        except CrawledLecture.DoesNotExist:
            return Response({"detail": "lecture_not_found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminLectureDetailSerializer(lecture)
        return Response(serializer.data, status=status.HTTP_200_OK)
