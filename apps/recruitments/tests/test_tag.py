from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestTagMockView:
    """Mock 기반 TagListView / TagDetailView 전체 테스트"""

    client: APIClient

    def setup_method(self) -> None:
        """테스트 초기 설정"""
        self.client = APIClient()

    # GET 전체 태그 조회
    def test_get_tags(self) -> None:
        response: Response = self.client.get("/api/recruitments/tags/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) == 5  # MOCK_TAGS 개수
        assert {"id": 1, "name": "Python"} in response.data

    # POST 새 태그 생성
    def test_post_tag_success(self) -> None:
        data: dict[str, str] = {"name": "FastAPI"}
        response: Response = self.client.post("/api/recruitments/tags/", data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "FastAPI"
        assert "id" in response.data

    # POST name 누락 → 400
    def test_post_tag_missing_name(self) -> None:
        response: Response = self.client.post("/api/recruitments/tags/", {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "태그 이름은 필수입니다" in str(response.data)

    # POST 중복된 태그 → 400
    def test_post_duplicate_tag(self) -> None:
        response: Response = self.client.post("/api/recruitments/tags/", {"name": "Python"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "이미 존재" in str(response.data)

    # GET 존재하지 않는 태그 → 404
    def test_get_tag_not_found(self) -> None:
        response: Response = self.client.get("/api/recruitments/tags/9999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "찾을 수 없습니다" in response.data["detail"]

    # PUT name 누락 → 400
    def test_put_tag_without_name(self) -> None:
        response: Response = self.client.put("/api/recruitments/tags/1/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "태그 이름은 필수" in response.data["error"]

    # PUT 존재하지 않는 태그 → 404
    def test_put_tag_not_found(self) -> None:
        response: Response = self.client.put("/api/recruitments/tags/9999/", {"name": "NewTag"}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "찾을 수 없습니다" in response.data["detail"]

    # DELETE 존재하지 않는 태그 → 404
    def test_delete_tag_not_found(self) -> None:
        response: Response = self.client.delete("/api/recruitments/tags/9999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "찾을 수 없습니다" in response.data["detail"]
