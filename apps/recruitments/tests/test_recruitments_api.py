from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.recruitments.models.recruitments import Recruitment
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class RecruitmentAPITestCase(APITestCase):
    """Recruitment CRUD API 실제 DB 기반 테스트"""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            birthday=date(2000, 1, 1),
        )
        self.client.force_authenticate(user=self.user)

        now = timezone.now()
        # 스터디 그룹 생성
        self.study_group = StudyGroup.objects.create(
            name="테스트 그룹",
            introduction="테스트 설명",
            max_headcount=5,
            start_at=now,
            end_at=now + timedelta(days=7),
        )
        # 그룹 리더 등록
        self.group_leader = GroupMember.objects.create(
            study_group=self.study_group,
            user=self.user,
            is_leader=True,
        )

        # 모집글 생성
        self.recruitment = Recruitment.objects.create(
            study_group=self.study_group,
            author=self.user,
            title="테스트 모집글",
            content="테스트용입니다.",
            estimated_fee=10000,
            expected_headcount=5,
            close_at=now + timedelta(days=7),
        )

        self.list_url = reverse("recruitment-list-create")

    def test_create_recruitment(self) -> None:
        data = {
            "title": "새 모집글",
            "content": "설명 내용",
            "estimated_fee": 15000,
            "expected_headcount": 3,
            "author": self.user.id,
            "study_group": self.study_group.id,
        }
        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Recruitment.objects.count(), 2)

    def test_get_recruitment_list(self) -> None:
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), Recruitment.objects.count())

    def test_get_recruitment_detail(self) -> None:
        detail_url = reverse("recruitment-detail", args=[self.recruitment.id])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], self.recruitment.title)

    def test_update_recruitment(self) -> None:
        detail_url = reverse("recruitment-detail", args=[self.recruitment.id])
        update_data = {"title": "수정 모집글", "content": "수정 내용", "estimated_fee": 12000, "expected_headcount": 4}
        response = self.client.put(detail_url, update_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.recruitment.refresh_from_db()
        self.assertEqual(self.recruitment.title, "수정 모집글")

    def test_delete_recruitment(self) -> None:
        detail_url = reverse("recruitment-detail", args=[self.recruitment.id])
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recruitment.objects.filter(id=self.recruitment.id).exists())
