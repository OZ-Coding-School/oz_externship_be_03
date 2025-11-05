from typing import Any

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.bookmark import Bookmark
from apps.recruitments.serializers.bookmark import BookmarkSerializer
from apps.recruitments.services.bookmark import create_bookmark


class BookmarkListCreateAPIView(APIView):
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(tags=["Bookmarks"], summary="북마크 생성 API")
    def post(self, request: Request) -> Response:
        """북마크 생성"""
        if isinstance(request.user, AnonymousUser):
            return Response({"detail": "로그인이 필요합니다."}, status=status.HTTP_401_UNAUTHORIZED)

        recruitment_id = request.data.get("recruitment_id")
        if not recruitment_id:
            return Response({"detail": "recruitment_id는 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # Service 호출
        try:
            bookmark = create_bookmark(request.user, recruitment_id)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(bookmark)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["Bookmarks"], summary="북마크 목록 조회 API")
    def get(self, request: Request) -> Response:
        """북마크 목록 조회"""
        if isinstance(request.user, AnonymousUser):
            return Response({"detail": "로그인이 필요합니다."}, status=status.HTTP_401_UNAUTHORIZED)

        bookmarks = Bookmark.objects.filter(user=request.user).select_related("recruitment")
        serializer = self.serializer_class(bookmarks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BookmarkRetrieveDestroyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Bookmarks"], summary="북마크 삭제 API")
    def delete(self, request: Request, bookmark_uuid: str, *args: Any, **kwargs: Any) -> Response:
        """북마크 삭제"""
        if isinstance(request.user, AnonymousUser):
            return Response({"detail": "로그인이 필요합니다."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            bookmark: Bookmark = Bookmark.objects.get(uuid=bookmark_uuid, user=request.user)
        except Bookmark.DoesNotExist:
            return Response({"detail": "해당 북마크를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        bookmark.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
