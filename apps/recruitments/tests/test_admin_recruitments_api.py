from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recruitments.models import Recruitment
from apps.users.models import User


class AdminRecruitmentAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.admin_user = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            birthday=date(1990, 1, 1),
            nickname="관리자",
            phone_number="01012345678",
        )
        self.client.force_authenticate(user=self.admin_user)

        self.recruitment = Recruitment.objects.create(
            author=self.admin_user,
            title="테스트 공고",
            content="테스트용 공고 내용입니다.",
            estimated_fee=10000,
            expected_headcount=3,
            views_count=15,
        )

    def test_admin_list_recruitments(self) -> None:
        url = reverse("admin_recruitment_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()[0]["title"], "테스트 공고")

    def test_admin_filter_by_is_closed(self) -> None:
        self.recruitment.is_closed = True
        self.recruitment.save()
        url = f"{reverse('admin_recruitment_list')}?is_closed=true"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.json():
            self.assertTrue(item["is_closed"])

    def test_admin_retrieve_recruitment(self) -> None:
        url = reverse("admin_recruitment_detail", args=[self.recruitment.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["title"], "테스트 공고")

    def test_admin_delete_recruitment(self) -> None:
        url = reverse("admin_recruitment_detail", args=[self.recruitment.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recruitment.objects.filter(id=self.recruitment.id).exists())

    def test_non_admin_forbidden(self) -> None:
        user = User.objects.create_user(
            email="user@test.com",
            password="1234",
            birthday=date(1995, 5, 5),
            nickname="일반유저",
            phone_number="01099998888",
        )
        self.client.force_authenticate(user=user)
        url = reverse("admin_recruitment_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
