from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recruitments.models import Recruitment, RecruitmentTag, Tag

User = get_user_model()


class TestRecruitmentTagView(TestCase):
    """RecruitmentTagListCreateView 테스트 (DB 기반, 페이지네이션 포함)"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            nickname="tester",
            birthday=date(2000, 1, 1),
        )
        self.recruitment = Recruitment.objects.create(
            author=self.user,
            title="테스트 공고",
            content="내용",
            estimated_fee=10000,
            expected_headcount=5,
        )
        self.url = reverse(
            "recruitment-tag-list",
            kwargs={"recruitment_id": self.recruitment.id},
        )

    # GET 테스트

    def test_get_tags_empty(self) -> None:
        """태그가 없을 때 빈 결과 반환"""
        response: Any = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_get_tags_with_data(self) -> None:
        """특정 공고에 연결된 태그 목록 조회"""
        tag1 = Tag.objects.create(name="Django")
        tag2 = Tag.objects.create(name="React")
        RecruitmentTag.objects.create(recruitment=self.recruitment, tag=tag1)
        RecruitmentTag.objects.create(recruitment=self.recruitment, tag=tag2)

        response: Any = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = [tag["name"] for tag in response.data["results"]]
        self.assertIn("Django", results)
        self.assertIn("React", results)

    def test_get_tags_with_custom_page_size(self) -> None:
        """page_size 파라미터로 페이지 크기 조절"""
        tags = [Tag.objects.create(name=f"Tag{i}") for i in range(10)]
        for tag in tags:
            RecruitmentTag.objects.create(recruitment=self.recruitment, tag=tag)

        response: Any = self.client.get(f"{self.url}?page_size=3")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 10)
        self.assertEqual(len(response.data["results"]), 3)

    # POST 테스트

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
        self.assertTrue("required" in str(response.data).lower() or "필수" in str(response.data))

    def test_post_duplicate_tag(self) -> None:
        """이미 존재하는 태그 재사용 시 201"""
        Tag.objects.create(name="Python")
        response: Any = self.client.post(self.url, {"name": "Python"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Python")
        # 태그는 중복 생성되지 않아야 함 (하나만 존재)
        self.assertEqual(Tag.objects.filter(name="Python").count(), 1)
        # RecruitmentTag 관계는 정확히 하나 생성되어야 함
        self.assertTrue(RecruitmentTag.objects.filter(recruitment=self.recruitment, tag__name="Python").exists())

    def test_post_already_linked_tag(self) -> None:
        """이미 연결된 태그 재등록 시 400"""
        tag = Tag.objects.create(name="Django")
        RecruitmentTag.objects.create(recruitment=self.recruitment, tag=tag)

        response: Any = self.client.post(self.url, {"name": "Django"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 이 공고에", response.data["detail"])

    def test_post_missing_recruitment_id(self) -> None:
        """recruitment_id 누락 시 404"""
        invalid_url = "/api/v1/recruitments/tags/"  # 잘못된 경로
        response: Any = self.client.post(invalid_url, {"name": "FastAPI"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
