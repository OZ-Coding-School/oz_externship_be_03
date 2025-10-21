import random
from typing import List

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.utils.pagination_mixin import PaginationHandlerMixin
from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.serializers.bookmark_serializers import (
    LectureBookmarkListSerializer,
)


class LectureBookmarkListAPIView(APIView, PaginationHandlerMixin):
    """북마크된 강의 목록 조회 API 뷰. (Mock 데이터 사용)"""

    permission_classes = [AllowAny]  # TODO: 기능 구현 후 권한 변경
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["Lectures"],
        summary="북마크한 강의 목록 조회 API (Mock)",
        responses={200: LectureBookmarkListSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        # 1. Mock CrawledLecture 객체 생성
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
                average_rating=random.uniform(3.5, 5.0),
                duration=random.randint(60, 300),
                url_link="https://mock.com/course/mock",
                description="북마크된 강의의 간략 설명",
            )
            for i in range(1, 51)
        ]

        # 2. Mock LectureBookmark 객체 생성
        mock_bookmarks: List[LectureBookmark] = [
            LectureBookmark(
                id=i,
                lecture=mock_lectures[i - 1],
                user_id=1,
            )
            for i in range(1, 51)
        ]

        # 3. 페이지네이션 처리
        # self.paginate_queryset은 PaginationHandlerMixin으로부터 상속받은 메서드.
        page = self.paginate_queryset(mock_bookmarks)
        if page is not None:
            # 4. 페이지네이션된 데이터만 직렬화
            serializer = LectureBookmarkListSerializer(page, many=True)
            # self.get_paginated_response 역시 PaginationHandlerMixin으로부터 상속받았습니다.
            return self.get_paginated_response(serializer.data)

        # 페이지네이터가 없을 경우 전체 데이터 직렬화 후 반환
        serializer = LectureBookmarkListSerializer(mock_bookmarks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LectureBookmarkButtonAPIView(APIView):
    """북마크 추가/삭제 API 뷰. (Mock 랜덤 응답)"""

    permission_classes = [AllowAny]  # TODO: 기능 구현 후 권한 변경
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["Lectures"],
        summary="북마크 추가/삭제 API (Mock 랜덤 응답)",
        parameters=[
            OpenApiParameter(
                name="lecture_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="북마크를 추가/삭제할 강의 ID",
            )
        ],
        responses={
            201: {
                "description": "북마크가 추가되었습니다.",
                "content": {"application/json": {"example": {"detail": "북마크가 추가되었습니다."}}},
            },
            200: {
                "description": "북마크가 삭제되었습니다.",
                "content": {"application/json": {"example": {"detail": "북마크가 삭제되었습니다."}}},
            },
            404: {
                "description": "존재하지 않는 강의입니다.",
                "content": {"application/json": {"example": {"error": "존재하지 않는 강의입니다."}}},
            },
        },
    )
    def post(self, request: Request, lecture_id: int) -> Response:
        """
        북마크 추가/삭제 로직을 구현합니다.
        Path Parameter(lecture_id)와 request.user를 사용합니다.
        """
        # 404 Mock: lecture_id가 999면 404를 반환한다고 가정
        if lecture_id == 999:
            return Response({"error": "존재하지 않는 강의입니다."}, status=status.HTTP_404_NOT_FOUND)

        # 랜덤으로 추가 (201) 또는 삭제 (200) 응답 발생
        if random.choice([True, False]):
            # TODO: 실제 구현 시에는 여기서 북마크 객체 생성 로직이 들어갑니다.
            return Response({"detail": "북마크가 추가되었습니다."}, status=status.HTTP_201_CREATED)
        else:
            # TODO: 실제 구현 시에는 여기서 북마크 객체 삭제 로직이 들어갑니다.
            return Response({"detail": "북마크가 삭제되었습니다."}, status=status.HTTP_200_OK)
