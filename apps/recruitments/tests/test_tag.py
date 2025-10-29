from typing import Any

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class TestTagMockView(TestCase):
    """RecruitmentTagListView 테스트 (Mock 기반, 페이지네이션 적용 버전)"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("tag-list")

    # 전체 태그 목록 조회 (페이지네이션 대응)
    def test_get_tags(self) -> None:
        response: Any = self.client.get(self.url)  # 경로 수정
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 페이지네이션 구조 검증
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertGreater(len(response.data["results"]), 0)
        self.assertIn("Python", str(response.data))

    # 태그 생성 성공
    def test_post_tag_success(self) -> None:
        data: dict[str, str] = {"name": "FastAPI"}
        response: Any = self.client.post(self.url, data)  # 경로 수정
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "FastAPI")
        self.assertIn("id", response.data)

    # 태그 이름 누락 → 400
    def test_post_tag_missing_name(self) -> None:
        response: Any = self.client.post(self.url, {})  # 경로 수정
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("태그 이름은 필수", str(response.data))

    # 중복된 태그 → 400
    def test_post_duplicate_tag(self) -> None:
        response: Any = self.client.post(self.url, {"name": "Python"})  # 경로 수정
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 존재", str(response.data))
