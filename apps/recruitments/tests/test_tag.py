from typing import Any

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class TestTagMockView(TestCase):
    """TagListView / TagDetailView 테스트 (Mock 기반)"""

    def setUp(self) -> None:
        self.client = APIClient()

    # 전체 태그 조회
    def test_get_tags(self) -> None:
        response: Any = self.client.get("/api/tags/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 5)
        self.assertIn({"id": 1, "name": "Python"}, response.data)  # ← ✅ 여기 수정됨

    # 태그 생성 성공
    def test_post_tag_success(self) -> None:
        data: dict[str, str] = {"name": "FastAPI"}
        response: Any = self.client.post("/api/tags/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "FastAPI")
        self.assertIn("id", response.data)

    # 태그 이름 누락 → 400
    def test_post_tag_missing_name(self) -> None:
        response: Any = self.client.post("/api/tags/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("태그 이름은 필수입니다", str(response.data))

    # 중복된 태그 → 400
    def test_post_duplicate_tag(self) -> None:
        response: Any = self.client.post("/api/tags/", {"name": "Python"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 존재", str(response.data))

    # 존재하지 않는 태그 조회 → 404
    def test_get_tag_not_found(self) -> None:
        response: Any = self.client.get("/api/tags/9999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("찾을 수 없습니다", str(response.data))

    # 태그 수정 시 이름 누락 → 400
    def test_put_tag_without_name(self) -> None:
        response: Any = self.client.put("/api/tags/1/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("태그 이름은 필수", str(response.data))

    # 존재하지 않는 태그 수정 → 404
    def test_put_tag_not_found(self) -> None:
        response: Any = self.client.put("/api/tags/9999/", {"name": "NewTag"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("찾을 수 없습니다", str(response.data))

    # 존재하지 않는 태그 삭제 → 404
    def test_delete_tag_not_found(self) -> None:
        response: Any = self.client.delete("/api/tags/9999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("찾을 수 없습니다", str(response.data))

    # 정상 삭제 → 200 OK
    def test_delete_tag_success(self) -> None:
        response: Any = self.client.delete("/api/tags/1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("삭제 완료", str(response.data))
