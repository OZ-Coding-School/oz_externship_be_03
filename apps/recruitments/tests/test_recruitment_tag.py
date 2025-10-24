from typing import Any

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class TestRecruitmentTagView(TestCase):
    """Mock 기반 RecruitmentTagListView 테스트"""

    def setUp(self) -> None:
        self.client = APIClient()

    # GET tags 성공
    def test_get_recruitment_tags_success(self) -> None:
        response: Any = self.client.get("/api/recruitments/101/tags/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        tag_names = [tag["tag"] for tag in response.data]
        self.assertIn("Python", tag_names)
        self.assertIn("Django", tag_names)

    # GET tags 404
    def test_get_recruitment_tags_not_found(self) -> None:
        response: Any = self.client.get("/api/recruitments/999/tags/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("이 구인 공고에 연결된 태그가 없습니다", str(response.data))

    # POST tag 성공
    def test_post_recruitment_tag(self) -> None:
        data: dict[str, str] = {"tag": "FastAPI"}
        response: Any = self.client.post("/api/recruitments/101/tags/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["tag"], "FastAPI")
        self.assertEqual(response.data["recruitment"], 101)
        self.assertIn("id", response.data)

    # DELETE tag 성공
    def test_delete_recruitment_tag_success(self) -> None:
        response: Any = self.client.delete("/api/recruitments/101/tags/1/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIn("태그가 성공적으로 삭제되었습니다", str(response.data))

    # DELETE tag 404
    def test_delete_recruitment_tag_not_found(self) -> None:
        response: Any = self.client.delete("/api/recruitments/101/tags/999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("삭제할 태그를 찾을 수 없습니다", str(response.data))
