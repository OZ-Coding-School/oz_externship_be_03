from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.serializers.tag import TagSerializer


@extend_schema(tags=["Tags"])
class TagListView(APIView):
    permission_classes = [AllowAny]

    MOCK_TAGS: list[dict[str, str]] = [
        {"id": "1", "name": "Python"},
        {"id": "2", "name": "Django"},
        {"id": "3", "name": "JavaScript"},
        {"id": "4", "name": "AI"},
        {"id": "5", "name": "Frontend"},
    ]

    def get(self, request: Request) -> Response:
        serializer = TagSerializer(data=self.MOCK_TAGS, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        name = request.data.get("name")
        if not isinstance(name, str) or not name:
            return Response({"error": "태그 이름은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        if any(tag["name"].lower() == name.lower() for tag in self.MOCK_TAGS):
            return Response({"error": "이미 존재하는 태그입니다."}, status=status.HTTP_400_BAD_REQUEST)

        new_tag = {"id": str(len(self.MOCK_TAGS) + 1), "name": name}
        return Response(new_tag, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Tags"])
class TagDetailView(APIView):
    permission_classes = [AllowAny]

    MOCK_TAGS: list[dict[str, str]] = [
        {"id": "1", "name": "Python"},
        {"id": "2", "name": "Django"},
        {"id": "3", "name": "JavaScript"},
        {"id": "4", "name": "AI"},
        {"id": "5", "name": "Frontend"},
    ]

    def _get_tag(self, tag_id: int) -> dict[str, str] | None:
        return next((t for t in self.MOCK_TAGS if int(t["id"]) == tag_id), None)

    def get(self, request: Request, tag_id: int) -> Response:
        tag = self._get_tag(tag_id)
        if not tag:
            return Response({"detail": "해당 태그를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        serializer = TagSerializer(data=tag)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request: Request, tag_id: int) -> Response:
        name = request.data.get("name")
        if not isinstance(name, str) or not name:
            return Response({"error": "태그 이름은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        tag = self._get_tag(tag_id)
        if not tag:
            return Response({"detail": "해당 태그를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        tag["name"] = name
        return Response(tag, status=status.HTTP_200_OK)

    def delete(self, request: Request, tag_id: int) -> Response:
        tag = self._get_tag(tag_id)
        if not tag:
            return Response({"detail": "해당 태그를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"detail": f"{tag_id}번 태그 삭제 완료"}, status=status.HTTP_204_NO_CONTENT)
