from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.recruitments.models import Bookmark, Recruitment
from apps.studies.models import StudyGroup

User = get_user_model()


class RecruitmentBookmarkAPITestCase(APITestCase):
    """
    REQ-RECM-010 ~ 011
    북마크 추가/삭제 및 북마크 목록 조회 테스트
    """

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="bookmark_tester@example.com",
            password="password123",
            name="북마크유저",
            nickname="user1",
            phone_number="01012345678",
            gender="M",
            birthday="1999-01-01",
        )

        self.study_group = StudyGroup.objects.create(
            name="Django 입문 스터디",
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=30),
        )
        self.client.force_authenticate(user=self.user)

        # 기본 공고 데이터 생성
        self.recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="테스트용 공고",
            content="본문",
            estimated_fee=10000,
            expected_headcount=3,
            close_at="2025-12-31T23:59:00Z",
        )

        # 북마크 관련 URL
        self.toggle_url = reverse("recruitments:bookmark-toggle", kwargs={"recruitment_uuid": self.recruitment.uuid})
        self.list_url = reverse("recruitments:bookmark-list")

    def test_010_toggle_bookmark_add(self) -> None:
        """REQ-RECM-010 — 북마크 추가"""
        response = self.client.post(self.toggle_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_bookmarked"])
        self.assertTrue(Bookmark.objects.filter(user=self.user, recruitment=self.recruitment).exists())
        self.assertEqual(response.data["message"], "북마크가 추가되었습니다.")

    def test_010_toggle_bookmark_remove(self) -> None:
        """REQ-RECM-010 — 북마크 해제"""
        # 먼저 추가
        Bookmark.objects.create(user=self.user, recruitment=self.recruitment)
        response = self.client.post(self.toggle_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_bookmarked"])
        self.assertFalse(Bookmark.objects.filter(user=self.user, recruitment=self.recruitment).exists())
        self.assertEqual(response.data["message"], "북마크가 해제되었습니다.")

    def test_011_bookmarked_list(self) -> None:
        """REQ-RECM-011 — 북마크한 공고 목록 조회"""
        # 북마크 추가
        Bookmark.objects.create(user=self.user, recruitment=self.recruitment)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        results = response.data["results"]
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["title"], self.recruitment.title)
        self.assertIn("bookmark_count", results[0])
