from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestRecruitmentTagView:
    """Mock 기반 RecruitmentTagListView 테스트"""

    client: APIClient

    def setup_method(self) -> None:
        """테스트용 클라이언트 초기화"""
        self.client = APIClient()

    def test_get_recruitment_tags_success(self) -> None:
        """특정 구인 공고의 태그를 정상적으로 가져오는 경우"""
        response: Response = self.client.get("/api/recruitments/101/tags/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2  # Python, Django
        tag_names = [tag["tag"] for tag in response.data]
        assert "Python" in tag_names and "Django" in tag_names

    def test_get_recruitment_tags_not_found(self) -> None:
        """존재하지 않는 공고 ID로 조회 시 404 반환"""
        response: Response = self.client.get("/api/recruitments/999/tags/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "이 구인 공고에 연결된 태그가 없습니다" in str(response.data)

    def test_post_recruitment_tag(self) -> None:
        """새로운 태그를 특정 공고에 추가 (Mock 응답 확인)"""
        data: dict[str, str] = {"tag": "FastAPI"}
        response: Response = self.client.post("/api/recruitments/101/tags/", data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["tag"] == "FastAPI"
        assert response.data["recruitment"] == 101
        assert "id" in response.data

    def test_delete_recruitment_tag_success(self) -> None:
        """태그 삭제 성공(Mock 응답 확인)"""
        response: Response = self.client.delete("/api/recruitments/101/tags/1/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert "태그가 성공적으로 삭제되었습니다" in str(response.data)

    def test_delete_recruitment_tag_not_found(self) -> None:
        """삭제할 태그가 없는 경우 404 반환"""
        response: Response = self.client.delete("/api/recruitments/101/tags/999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "삭제할 태그를 찾을 수 없습니다" in str(response.data)
