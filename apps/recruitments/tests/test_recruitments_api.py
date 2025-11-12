from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.recruitments.models import Recruitment, Tag
from apps.studies.models import StudyGroup

User = get_user_model()


class RecruitmentAPITestCase(APITestCase):
    """
    REQ-RECM-001 ~ 007
    """

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            name="테스트유저",
            nickname="user2",
            phone_number="01011112222",
            gender="F",
            birthday="1998-05-10",
        )

        self.study_group = StudyGroup.objects.create(
            name="Django 입문 스터디",
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=30),
        )

        self.recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="테스트 공고",
            content="내용",
            estimated_fee=20000,
            expected_headcount=4,
        )
        self.client.force_authenticate(user=self.user)

        self.create_url = reverse("recruitments:list-create")  # POST, GET /api/v1/recruitments/
        self.user_list_url = reverse("recruitments:user-list")

    def test_001_create_recruitment(self) -> None:
        """스터디 구인 공고 작성 (REQ-RECM-001)"""
        data = {
            "title": "Django 스터디 모집합니다!",
            "content": "마크다운 기반 본문",
            "estimated_fee": 30000,
            "expected_headcount": 5,
            "close_at": "2025-12-01T23:59:00Z",
            "study_group_id": self.study_group.id,
            "tags": ["Django", "Python"],
        }

        response = self.client.post(self.create_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("title", response.data)
        self.assertEqual(response.data["title"], data["title"])
        self.assertTrue(Recruitment.objects.filter(title=data["title"]).exists())

    def test_002_list_recruitments(self) -> None:
        """공고 목록 조회 (REQ-RECM-003)"""
        Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="테스트 공고",
            content="본문",
            estimated_fee=20000,
            expected_headcount=3,
            close_at="2025-12-31T23:59:00Z",
        )

        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_003_get_detail(self) -> None:
        """공고 상세 조회 (REQ-RECM-006)"""
        recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="상세 테스트",
            content="상세 본문",
            estimated_fee=25000,
            expected_headcount=4,
            close_at="2025-12-31T23:59:00Z",
        )
        url = reverse("recruitments:detail", kwargs={"recruitment_id": recruitment.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], recruitment.title)
        self.assertIn("views_count", response.data)

    def test_004_update_recruitment(self) -> None:
        """공고 수정 (REQ-RECM-007)"""
        recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="수정 전 제목",
            content="본문",
            estimated_fee=10000,
            expected_headcount=2,
            close_at="2025-11-30T23:59:00Z",
        )
        url = reverse("recruitments:detail", kwargs={"recruitment_id": recruitment.id})
        data = {
            "title": "수정된 제목",
            "content": "수정된 본문",
            "estimated_fee": 20000,
            "expected_headcount": 3,
            "close_at": "2025-12-10T23:59:00Z",
        }

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recruitment.refresh_from_db()
        self.assertEqual(recruitment.title, "수정된 제목")

    def test_005_delete_recruitment(self) -> None:
        """공고 삭제 (REQ-RECM-009)"""
        recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="삭제 테스트",
            content="본문",
            estimated_fee=10000,
            expected_headcount=2,
            close_at="2025-12-01T23:59:00Z",
        )
        url = reverse("recruitments:detail", kwargs={"recruitment_id": recruitment.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recruitment.objects.filter(pk=recruitment.id).exists())
