from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestTagMockView:
    """Mock 기반 TagListView 테스트"""

    client: APIClient

    def setup_method(self) -> None:
        """테스트 초기 설정"""
        self.client = APIClient()

    def test_get_tags(self) -> None:
        """전체 태그 목록(Mock 데이터) 조회"""
        response: Response = self.client.get("/api/recruitments/tags/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) == 5  # MOCK_TAGS 개수
        assert {"id": 1, "name": "Python"} in response.data

    def test_post_tag_success(self) -> None:
        """새로운 태그 생성(Mock 응답 확인)"""
        data: dict[str, str] = {"name": "FastAPI"}
        response: Response = self.client.post("/api/recruitments/tags/", data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "FastAPI"
        assert "id" in response.data

    def test_post_tag_missing_name(self) -> None:
        """태그 이름이 누락된 경우 400 반환"""
        response: Response = self.client.post("/api/recruitments/tags/", {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "태그 이름은 필수입니다" in str(response.data)
