from typing import Any

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class TestTagMockView(TestCase):
    """Mock 기반 TagListView / TagDetailView 전체 테스트"""

    def setUp(self) -> None:
        """테스트 초기 설정"""
        self.client = APIClient()

    # GET 전체 태그 조회
    def test_get_tags(self) -> None:
        response: Any = self.client.get("/api/recruitments/tags/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 5)  # MOCK_TAGS 개수
        self.assertIn({"id": 1, "name": "Python"}, response.data)

    # POST 새 태그 생성
    def test_post_tag_success(self) -> None:
        data: dict[str, str] = {"name": "FastAPI"}
        response: Any = self.client.post("/api/recruitments/tags/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "FastAPI")
        self.assertIn("id", response.data)

    # POST name 누락 → 400
    def test_post_tag_missing_name(self) -> None:
        response: Any = self.client.post("/api/recruitments/tags/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("태그 이름은 필수입니다", str(response.data))

    # POST 중복된 태그 → 400
    def test_post_duplicate_tag(self) -> None:
        response: Any = self.client.post("/api/recruitments/tags/", {"name": "Python"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 존재", str(response.data))

    # GET 존재하지 않는 태그 → 404
    def test_get_tag_not_found(self) -> None:
        response: Any = self.client.get("/api/recruitments/tags/9999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("찾을 수 없습니다", response.data["detail"])

    # PUT name 누락 → 400
    def test_put_tag_without_name(self) -> None:
        response: Any = self.client.put("/api/recruitments/tags/1/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("태그 이름은 필수", response.data["error"])

    # PUT 존재하지 않는 태그 → 404
    def test_put_tag_not_found(self) -> None:
        response: Any = self.client.put("/api/recruitments/tags/9999/", {"name": "NewTag"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("찾을 수 없습니다", response.data["detail"])

    # DELETE 존재하지 않는 태그 → 404
    def test_delete_tag_not_found(self) -> None:
        response: Any = self.client.delete("/api/recruitments/tags/9999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("찾을 수 없습니다", response.data["detail"])
