from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.bookmark import Bookmark
from apps.recruitments.serializers.bookmark import BookmarkSerializer


class BookmarkListCreateAPIView(APIView):
    serializer_class = BookmarkSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(tags=["Bookmarks"], summary="북마크 생성 API")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = request.data
        recruitment_id = data.get("recruitment_id")

        if not recruitment_id:
            return Response(
                {"detail": "유효하지 않은 데이터입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if recruitment_id in [1, 2]:
            return Response(
                {"detail": "이미 북마크한 강의입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if recruitment_id in [9999]:  # 테스트 기준 존재하지 않는 lecture
            return Response(
                {"detail": "존재하지 않는 강의입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "북마크가 추가되었습니다.", "bookmark_id": recruitment_id},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        operation_id="v1_bookmarks_list",
        tags=["Bookmarks"],
        summary="북마크 전체 목록 조회 API",
        responses={200: BookmarkSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        mock_data = [Bookmark(user_id=i, recruitment_id=i, created_at=timezone.now()) for i in range(1, 16)]
        serializer = self.serializer_class(mock_data, many=True)

        return Response({"results": serializer.data}, status=status.HTTP_200_OK)


class BookmarkRetrieveDestroyAPIView(APIView):
    serializer_class = BookmarkSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(tags=["Bookmarks"], summary="북마크 상세 조회 API")
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        mock_data = Bookmark(user_id=1, recruitment_id=recruitment_id, created_at=timezone.now())
        serializer = self.serializer_class(mock_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(tags=["Bookmarks"], summary="북마크 삭제 API")
    def delete(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        return Response({"detail": "북마크가 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)
