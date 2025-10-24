from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.serializers.recruitment_tag import RecruitmentTagMockSerializer


@extend_schema_view(
    get=extend_schema(
        summary="특정 공고에 연결된 태그 목록 조회 (Mock)",
        description="특정 구인 공고(recruitment_id)에 연결된 모든 태그를 Mock 데이터로 반환합니다.",
    ),
    post=extend_schema(
        summary="특정 공고에 태그 추가 (Mock)",
        description="입력한 태그를 특정 구인 공고(recruitment_id)에 추가합니다.",
    ),
    delete=extend_schema(
        summary="특정 공고에서 태그 삭제 (Mock)",
        description="특정 구인 공고(recruitment_id)에서 tag_id에 해당하는 태그를 삭제합니다.",
    ),
)
class RecruitmentTagListView(APIView):
    """공고별 태그 관리 (Mock)"""

    permission_classes = [AllowAny]

    # recruitment_id → list[dict]
    MOCK_TAGS: dict[int, list[dict[str, Any]]] = {
        101: [
            {"id": 1, "recruitment": 101, "tag": "Python"},
            {"id": 2, "recruitment": 101, "tag": "Django"},
        ],
        102: [{"id": 1, "recruitment": 102, "tag": "React"}],
    }

    def get(self, request: Request, recruitment_id: int) -> Response:
        """특정 공고에 연결된 태그 목록 조회"""
        tags = self.MOCK_TAGS.get(recruitment_id)
        if not tags:
            return Response(
                {"detail": "이 구인 공고에 연결된 태그가 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RecruitmentTagMockSerializer(tags, many=True)
        return Response(serializer.data)

    def post(self, request: Request, recruitment_id: int) -> Response:
        """특정 공고에 태그 추가"""
        tag_name: str | None = request.data.get("tag")
        if not tag_name:
            return Response(
                {"error": "태그 이름은 필수입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_tag = {
            "id": len(self.MOCK_TAGS.get(recruitment_id, [])) + 1,
            "recruitment": recruitment_id,
            "tag": tag_name,
        }

        serializer = RecruitmentTagMockSerializer(new_tag)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request: Request, recruitment_id: int, tag_id: int) -> Response:
        """특정 공고에서 태그 삭제"""
        tags = self.MOCK_TAGS.get(recruitment_id)
        if not tags:
            return Response(
                {"error": "삭제할 태그를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        tag = next((t for t in tags if t["id"] == tag_id), None)
        if not tag:
            return Response(
                {"error": "삭제할 태그를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"detail": "태그가 성공적으로 삭제되었습니다."},
            status=status.HTTP_204_NO_CONTENT,
        )
