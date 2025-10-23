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

    MOCK_DUPLICATE_IDS = [2, 4]
    MOCK_NONEXISTENT_IDS = [9999]

    @extend_schema(tags=["Bookmarks"], summary="북마크 생성 API")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        recruitment_id = serializer.validated_data.get("recruitment_id")
        if recruitment_id is None:
            return Response({"detail": "recruitment_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        if recruitment_id in self.MOCK_DUPLICATE_IDS:
            return Response(
                {"detail": "이미 북마크한 강의입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if recruitment_id in self.MOCK_NONEXISTENT_IDS:
            return Response(
                {"detail": "존재하지 않는 강의입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mock_bookmark = Bookmark(user_id=1, recruitment_id=recruitment_id, created_at=timezone.now())
        return Response(
            self.serializer_class(mock_bookmark).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="북마크 목록 조회 API ")
    def get(self, request: Request) -> Response:
        mock_data = [Bookmark(user_id=1, recruitment_id=i, created_at=timezone.now()) for i in range(1, 6)]
        serializer = self.serializer_class(mock_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BookmarkRetrieveDestroyAPIView(APIView):

    serializer_class = BookmarkSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser]

    @extend_schema(tags=["Bookmarks"], summary="북마크 상세 조회 API")
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        mock_bookmark = Bookmark(
            user_id=1,
            recruitment_id=recruitment_id,
            created_at=timezone.now(),
        )
        serializer = self.serializer_class(mock_bookmark)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(tags=["Bookmarks"], summary="북마크 삭제 API")
    def delete(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        return Response(
            {"detail": f"북마크(recruitment_id={recruitment_id})가 삭제되었습니다."},
            status=status.HTTP_204_NO_CONTENT,
        )
