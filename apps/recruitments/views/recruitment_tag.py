from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.serializers.recruitment_tag import RecruitmentTagSerializer


class RecruitmentTagListView(APIView):
    """Mock 데이터를 사용한 구인 공고 태그 API"""

    # 임시 Mock 데이터
    MOCK_RECRUITMENT_TAGS = [
        {"id": 1, "recruitment": 101, "tag": "Python", "created_at": "2025-10-01", "updated_at": "2025-10-02"},
        {"id": 2, "recruitment": 101, "tag": "Django", "created_at": "2025-10-03", "updated_at": "2025-10-04"},
        {"id": 3, "recruitment": 102, "tag": "JavaScript", "created_at": "2025-10-05", "updated_at": "2025-10-06"},
    ]

    def get(self, request: Request, recruitment_id: int) -> Response:
        """특정 구인 공고에 연결된 모든 태그를 (Mock 데이터로) 가져옵니다."""
        # recruitment_id로 필터링된 Mock 데이터만 가져오기
        filtered_tags = [tag for tag in self.MOCK_RECRUITMENT_TAGS if tag["recruitment"] == recruitment_id]

        if not filtered_tags:
            raise NotFound(detail="이 구인 공고에 연결된 태그가 없습니다. (mock data)")

        serializer = RecruitmentTagSerializer(data=filtered_tags, many=True)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request, recruitment_id: int) -> Response:
        """새로운 태그를 특정 구인 공고에 추가합니다. (Mock 데이터 기반)"""
        data = request.data.copy()
        data["recruitment"] = recruitment_id

        serializer = RecruitmentTagSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        # DB 저장 대신 Mock 리스트에 추가한 것처럼 응답만 반환
        mock_created = {
            "id": len(self.MOCK_RECRUITMENT_TAGS) + 1,
            **serializer.validated_data,
        }

        return Response(mock_created, status=status.HTTP_201_CREATED)

    def delete(self, request: Request, recruitment_id: int, tag_id: int) -> Response:
        """특정 구인 공고에서 태그를 삭제합니다. (Mock 데이터 기반)"""
        # 실제 DB 접근 없이 리스트 내에서 존재 여부만 확인
        exists = any(
            tag for tag in self.MOCK_RECRUITMENT_TAGS if tag["recruitment"] == recruitment_id and tag["id"] == tag_id
        )

        if not exists:
            raise NotFound(detail="삭제할 태그를 찾을 수 없습니다. (mock data)")

        # 삭제 성공 응답만 반환 (실제 데이터 변경 없음)
        return Response(
            {"detail": "태그가 성공적으로 삭제되었습니다. (mock data)"},
            status=status.HTTP_204_NO_CONTENT,
        )
