import random
from typing import List, Optional

from drf_spectacular.utils import extend_schema
from rest_framework import parsers, serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.serializers.bookmark_serializers import (
    LectureBookmarkCreateSerializer,
    LectureBookmarkListSerializer,
)


class LectureBookmarkListCreateView(APIView):
    """
    로그인 유저 북마크 목록 조회 및 북마크 추가 API (Mock 데이터 사용)
    GET: 목록 조회
    POST: 북마크 추가
    """

    permission_classes = [AllowAny]  # TODO: 기능 구현 후 권한 변경
    parser_classes = [parsers.JSONParser]
    pagination_class = PageNumberPagination
    page_size = 10

    @extend_schema(
        tags=["Lectures"],
        summary="로그인 유저 북마크 목록 조회 및 북마크 추가 API (Mock)",
        responses={
            200: LectureBookmarkListSerializer(many=True),
            201: {"description": "북마크가 추가되었습니다."},
            400: {"description": "잘못된 요청"},
            404: {"description": "존재하지 않는 강의입니다."},
        },
        request=LectureBookmarkCreateSerializer,
    )
    def get(self, request: Request) -> Response:
        mock_lectures: List[CrawledLecture] = [
            CrawledLecture(
                id=i,
                uuid=f"123e4567-e89b-12d3-a456-4266141740{i:02d}",
                title=f"Mock 북마크 강의 {i}",
                instructor=f"강사 {i}",
                thumbnail_img_url="https://mock.com/thumb.jpg",
                difficulty="NORMAL",
                original_price=120000 + i * 100,
                discount_price=100000 + i * 100,
                platform="INFLEARN",
                average_rating=round(random.uniform(3.5, 5.0), 2),
                duration=random.randint(60, 300),
                url_link="https://mock.com/course/mock",
                description="북마크된 강의의 간략 설명",
            )
            for i in range(1, 51)
        ]

        mock_bookmarks: List[LectureBookmark] = [
            LectureBookmark(id=i, lecture=mock_lectures[i - 1], user_id=request.user.id or 1) for i in range(1, 51)
        ]

        paginator = self.pagination_class()
        page: Optional[List[LectureBookmark]] = paginator.paginate_queryset(mock_bookmarks, request, view=self)  # type: ignore
        if page is not None:
            serializer = LectureBookmarkListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = LectureBookmarkListSerializer(mock_bookmarks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        serializer = LectureBookmarkCreateSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            bookmark = serializer.save()
        except serializers.ValidationError as e:
            return Response({"detail": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "북마크가 추가되었습니다."}, status=status.HTTP_201_CREATED)


class LectureBookmarkDeleteView(APIView):
    """북마크 삭제 API (Mock 응답)"""

    permission_classes = [AllowAny]  # TODO: 기능 구현 후 권한 변경
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["Lectures"],
        summary="강의 북마크 삭제 API (Mock)",
        responses={
            204: {"description": "북마크가 삭제되었습니다."},
            404: {"description": "존재하지 않는 북마크입니다."},
        },
    )
    def delete(self, request: Request, lecture_id: int) -> Response:
        if lecture_id == 999:
            return Response({"error": "존재하지 않는 북마크입니다."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # def delete(self, request, bookmark_id: int):
    #     try:
    #         obj = LectureBookmark.objects.get(id=bookmark_id)
    #     except LectureBookmark.DoesNotExist:
    #         return Response({"error": "북마크를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    #     obj.delete()
    #     return Response(status=status.HTTP_204_NO_CONTENT)
