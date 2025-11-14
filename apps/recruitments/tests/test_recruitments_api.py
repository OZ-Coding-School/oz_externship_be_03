from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.recruitments.models import Recruitment
from apps.studies.models import StudyGroup

User = get_user_model()


class RecruitmentAPITestCase(APITestCase):
    """REQ-RECM-001 ~ 009"""

    def setUp(self) -> None:
        # 사용자 설정
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

        # 스터디 그룹
        self.study_group = StudyGroup.objects.create(
            name="Django 입문 스터디",
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=30),
        )

        # 기본 공고
        self.recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="테스트 공고",
            content="내용",
            estimated_fee=20000,
            expected_headcount=4,
        )

        self.client.force_authenticate(user=self.user)

        self.create_url = reverse("recruitments:list-create")
        self.user_list_url = reverse("recruitments:user-list")
        self.presign_url = reverse("recruitments:presigned-url")

    def test_001_create_recruitment(self) -> None:
        """공고 생성"""
        data = {
            "title": "Django 스터디 모집합니다!",
            "content": "마크다운 본문",
            "estimated_fee": 30000,
            "expected_headcount": 5,
            "close_at": "2025-12-01T23:59:00Z",
            # Serializer 요구사항에 따라 study_group_id로 전송
            "study_group_id": self.study_group.id,
            "tags": ["Django", "Python"],
        }

        # multipart/form-data
        response = self.client.post(self.create_url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], data["title"])

    def test_002_list_recruitments(self) -> None:
        """공고 목록 조회"""
        Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="목록 테스트",
            content="본문",
            estimated_fee=20000,
            expected_headcount=3,
            close_at="2025-12-31T23:59:00Z",
        )

        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_003_detail(self) -> None:
        """공고 상세 조회"""
        recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="상세 테스트",
            content="본문",
            estimated_fee=20000,
            expected_headcount=4,
        )
        url = reverse("recruitments:detail", kwargs={"recruitment_uuid": recruitment.uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], recruitment.title)

    def test_004_update_recruitment(self) -> None:
        """공고 수정"""
        recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="수정 전 제목",
            content="본문",
            estimated_fee=10000,
            expected_headcount=2,
        )
        url = reverse("recruitments:detail", kwargs={"recruitment_uuid": recruitment.uuid})

        # PUT이므로 모든 필드 필요
        data = {
            "title": "수정된 제목",
            "content": "수정된 본문",
            "estimated_fee": 20000,
            "expected_headcount": 3,
            "close_at": "2025-12-10T23:59:00Z",
            "study_group_id": self.study_group.id,
        }

        response = self.client.put(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        recruitment.refresh_from_db()
        self.assertEqual(recruitment.title, "수정된 제목")

    def test_005_delete_recruitment(self) -> None:
        """공고 삭제"""
        recruitment = Recruitment.objects.create(
            author=self.user,
            study_group=self.study_group,
            title="삭제 테스트",
            content="본문",
            estimated_fee=10000,
            expected_headcount=2,
        )
        url = reverse("recruitments:detail", kwargs={"recruitment_uuid": recruitment.uuid})

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recruitment.objects.filter(pk=recruitment.id).exists())

    def test_006_presigned_url(self) -> None:
        """presigned-url API"""
        response = self.client.get(self.presign_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("url", response.data)
