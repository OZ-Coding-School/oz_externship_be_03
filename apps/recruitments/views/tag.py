from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.serializers.tag import TagSerializer


class TagListView(APIView):
    def get(self, request: Request) -> Response:
        mock_tags = [
            {"id": 1, "name": "Python"},
            {"id": 2, "name": "Django"},
            {"id": 3, "name": "JavaScript"},
        ]
        serializer: TagSerializer = TagSerializer(data=mock_tags, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        new_tag_name = request.data.get("name")
        if not new_tag_name:
            return Response({"error": "Tag name is required."}, status=status.HTTP_400_BAD_REQUEST)

        mock_tag = {"id": 4, "name": new_tag_name}
        serializer: TagSerializer = TagSerializer(data=mock_tag)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    def get(self, request: Request, tag_id: int) -> Response:
        mock_tags = [
            {"id": 1, "name": "Python"},
            {"id": 2, "name": "Django"},
            {"id": 3, "name": "JavaScript"},
        ]
        tag = next((t for t in mock_tags if t["id"] == tag_id), None)
        if not tag:
            raise NotFound(detail="Tag not found.")

        serializer: TagSerializer = TagSerializer(data=tag)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def put(self, request: Request, tag_id: int) -> Response:
        tag_name = request.data.get("name")
        if not tag_name:
            return Response({"error": "Tag name is required."}, status=status.HTTP_400_BAD_REQUEST)

        updated_tag = {"id": tag_id, "name": tag_name}
        serializer: TagSerializer = TagSerializer(data=updated_tag)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def delete(self, request: Request, tag_id: int) -> Response:
        return Response(
            {"detail": f"Tag {tag_id} deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )
