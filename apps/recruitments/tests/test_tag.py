from typing import Any

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recruitments.models import Tag


class TestRecruitmentTagView(TestCase):
    """RecruitmentTagListCreateView 테스트 (DB 기반, 페이지네이션 포함)"""

    def setUp(self) -> None:
        self.client = APIClient()
        # 실제 URL 이름에 맞게 수정
        self.recruitment_id = 1
        self.url = reverse("recruitment-tag-list", kwargs={"recruitment_id": self.recruitment_id})

    def test_get_tags_empty(self) -> None:
        """태그가 없을 때 빈 결과 반환"""
        response: Any = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 0)

    def test_post_tag_success(self) -> None:
        """태그 생성 성공"""
        data: dict[str, str] = {"name": "FastAPI"}
        response: Any = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "FastAPI")
        self.assertIn("id", response.data)
        self.assertTrue(Tag.objects.filter(name="FastAPI").exists())

    def test_post_tag_missing_name(self) -> None:
        """태그 이름 누락 시 400"""
        response: Any = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("태그 이름은 필수", str(response.data))

    def test_post_duplicate_tag(self) -> None:
        """중복된 태그 생성 시 400"""
        Tag.objects.create(name="Python")
        response: Any = self.client.post(self.url, {"name": "Python"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 존재", str(response.data))

    def test_get_tags_with_data(self) -> None:
        """태그가 존재할 때 목록 정상 조회"""
        Tag.objects.create(name="Django")
        Tag.objects.create(name="React")
        response: Any = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreater(response.data["count"], 0)
        self.assertIn("Django", str(response.data))
