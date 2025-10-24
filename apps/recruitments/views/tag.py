from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.serializers.tag import TagSerializer


class TagListView(APIView):
    """태그 목록(Mock)"""

    MOCK_TAGS = [
        {"id": 1, "name": "Python"},
        {"id": 2, "name": "Django"},
        {"id": 3, "name": "JavaScript"},
        {"id": 4, "name": "AI"},
        {"id": 5, "name": "Frontend"},
    ]

    def get(self, request: Request) -> Response:
        serializer = TagSerializer(data=self.MOCK_TAGS, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        name = request.data.get("name")
        if not name:
            return Response({"error": "태그 이름은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        tag = {"id": len(self.MOCK_TAGS) + 1, "name": name}
        return Response(tag, status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    """태그 상세(Mock)"""

    MOCK_TAGS = [
        {"id": 1, "name": "Python"},
        {"id": 2, "name": "Django"},
        {"id": 3, "name": "JavaScript"},
        {"id": 4, "name": "AI"},
        {"id": 5, "name": "Frontend"},
    ]

    def get(self, request: Request, tag_id: int) -> Response:
        tag = next((t for t in self.MOCK_TAGS if t["id"] == tag_id), None)
        if not tag:
            raise NotFound("해당 태그를 찾을 수 없습니다. (mock data)")

        serializer = TagSerializer(data=tag)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def put(self, request: Request, tag_id: int) -> Response:
        name = request.data.get("name")
        if not name:
            return Response({"error": "태그 이름은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        tag = next((t for t in self.MOCK_TAGS if t["id"] == tag_id), None)
        if not tag:
            raise NotFound("해당 태그를 찾을 수 없습니다. (mock data)")

        tag["name"] = name
        return Response(tag)

    def delete(self, request: Request, tag_id: int) -> Response:
        tag = next((t for t in self.MOCK_TAGS if t["id"] == tag_id), None)
        if not tag:
            raise NotFound("해당 태그를 찾을 수 없습니다. (mock data)")

        return Response({"detail": f"{tag_id}번 태그 삭제 완료 (mock data)"}, status=status.HTTP_204_NO_CONTENT)
