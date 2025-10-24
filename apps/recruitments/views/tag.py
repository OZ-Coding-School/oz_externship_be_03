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
    """전체 태그(Mock) 목록 조회 및 생성"""

    permission_classes = [AllowAny]
    serializer_class = TagSerializer

    MOCK_TAGS: list[dict[str, str]] = [
        {"id": "1", "name": "Python"},
        {"id": "2", "name": "Django"},
        {"id": "3", "name": "JavaScript"},
        {"id": "4", "name": "AI"},
        {"id": "5", "name": "Frontend"},
    ]

    # 전체 태그 목록 조회
    @extend_schema(
        summary="전체 태그 목록 조회 (Mock)",
        description="전체 태그(Mock 데이터)를 반환합니다.",
        responses={200: TagSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        serializer = TagSerializer(self.MOCK_TAGS, many=True)  # type: ignore[arg-type]
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 새로운 태그 생성
    @extend_schema(
        summary="새로운 태그 생성 (Mock)",
        description="입력된 이름으로 새로운 태그(Mock)를 생성합니다.",
        request=TagSerializer,
        responses={
            201: TagSerializer,
            400: {"example": {"error": "태그 이름은 필수입니다."}},
        },
    )
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
    """개별 태그(Mock) 조회, 수정, 삭제"""

    permission_classes = [AllowAny]
    serializer_class = TagSerializer

    MOCK_TAGS: list[dict[str, str]] = [
        {"id": "1", "name": "Python"},
        {"id": "2", "name": "Django"},
        {"id": "3", "name": "JavaScript"},
        {"id": "4", "name": "AI"},
        {"id": "5", "name": "Frontend"},
    ]

    def _get_tag(self, tag_id: int) -> dict[str, str] | None:
        return next((t for t in self.MOCK_TAGS if int(t["id"]) == tag_id), None)

    # 특정 태그 조회
    @extend_schema(
        summary="특정 태그 조회 (Mock)",
        description="특정 ID에 해당하는 태그(Mock)를 반환합니다.",
        responses={200: TagSerializer, 404: {"example": {"detail": "해당 태그를 찾을 수 없습니다."}}},
    )
    def get(self, request: Request, tag_id: int) -> Response:
        tag = self._get_tag(tag_id)
        if not tag:
            return Response({"detail": "해당 태그를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        serializer = TagSerializer(tag)  # type: ignore[arg-type]
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 태그 수정
    @extend_schema(
        summary="태그 수정 (Mock)",
        description="특정 태그의 이름을 수정합니다.",
        request=TagSerializer,
        responses={
            200: TagSerializer,
            400: {"example": {"error": "태그 이름은 필수입니다."}},
            404: {"example": {"detail": "해당 태그를 찾을 수 없습니다."}},
        },
    )
    def put(self, request: Request, tag_id: int) -> Response:
        name = request.data.get("name")
        if not isinstance(name, str) or not name:
            return Response({"error": "태그 이름은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        tag = self._get_tag(tag_id)
        if not tag:
            return Response({"detail": "해당 태그를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        tag["name"] = name
        return Response(tag, status=status.HTTP_200_OK)

    # 태그 삭제
    @extend_schema(
        summary="태그 삭제 (Mock)",
        description="특정 ID의 태그를 삭제합니다.",
        responses={
            200: {"example": {"detail": "태그 삭제 완료"}},
            404: {"example": {"detail": "해당 태그를 찾을 수 없습니다."}},
        },
    )
    def delete(self, request: Request, tag_id: int) -> Response:
        tag = self._get_tag(tag_id)
        if not tag:
            return Response({"detail": "해당 태그를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"detail": f"{tag_id}번 태그 삭제 완료"}, status=status.HTTP_200_OK)
