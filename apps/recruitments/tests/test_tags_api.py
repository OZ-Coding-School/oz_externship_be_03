from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.recruitments.models import Recruitment, Tag
from apps.studies.models import StudyGroup

User = get_user_model()


class RecruitmentTagAPITestCase(APITestCase):
    """REQ-RECM-002, 008"""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="tagtester@example.com",
            password="password123",
            name="태그유저",
            nickname="user3",
            phone_number="01099998888",
            gender="M",
            birthday="1997-03-03",
        )

        self.study_group = StudyGroup.objects.create(
            name="Django 입문 스터디",
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=30),
        )

        self.recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="태그용 공고",
            content="내용",
            estimated_fee=15000,
            expected_headcount=3,
        )
        self.tag_search_create_url = reverse("recruitments:tags-search-create")
        self.tag_add_for_recruitment_url = reverse(
            "recruitments:tags-search-add", kwargs={"recruitment_id": self.recruitment.id}
        )

    def test_002_tag_search(self) -> None:
        """REQ-RECM-002 — 태그 검색"""
        Tag.objects.create(name="Python")
        Tag.objects.create(name="Django")

        response = self.client.get(self.tag_search_create_url, {"keyword": "Py"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Python")

    def test_002_tag_create(self) -> None:
        """REQ-RECM-002 — 태그 신규 등록"""
        data = {"tags": ["AI", "DeepLearning"]}
        response = self.client.post(self.tag_search_create_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("created_tags", response.data)
        self.assertTrue(Tag.objects.filter(name="AI").exists())
        self.assertTrue(Tag.objects.filter(name="DeepLearning").exists())

    def test_008_tag_add_for_recruitment(self) -> None:
        """REQ-RECM-008 — 특정 공고에 태그 추가"""
        Tag.objects.create(name="Backend")
        Tag.objects.create(name="Python")

        data = {"tags": ["Backend", "Python"]}
        response = self.client.post(self.tag_add_for_recruitment_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("added_tags", response.data)
        self.assertEqual(set(response.data["added_tags"]), {"Backend", "Python"})
        self.assertEqual(response.data["recruitment_id"], self.recruitment.id)

    def test_008_tag_add_exceeds_limit(self) -> None:
        """REQ-RECM-008 — 공고당 태그 5개 초과 시 400 반환"""
        # 미리 5개 태그를 연결
        for i in range(5):
            tag = Tag.objects.create(name=f"Tag{i}")
            self.recruitment.tags.add(tag)

        data = {"tags": ["NewTag"]}
        response = self.client.post(self.tag_add_for_recruitment_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
