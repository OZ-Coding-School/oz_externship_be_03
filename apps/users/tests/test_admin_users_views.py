from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.enums import Reason
from apps.users.models import User, Withdrawal


class AdminWithdrawalListViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        self.admin_user: User = User.objects.create_superuser(
            email="admin@example.com",
            password="admin123",
            name="관리자",
            birthday="1990-01-01",
            gender="f",
            phone_number="01012345678",
            nickname="admin",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )

        self.normal_user: User = User.objects.create_user(
            email="user@example.com",
            password="user123",
            name="유저",
            birthday="1995-05-05",
            gender="m",
            phone_number="01087654321",
            nickname="user",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )

        Withdrawal.objects.create(
            user=self.normal_user,
            reason=Reason.PRIVACY_CONCERNS.value,
            reason_detail="테스트 탈퇴 사유",
            due_date="2025-12-31",
        )

    def test_admin_can_view_withdrawals(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("users:admin_withdrawal_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.json()["data"]
        self.assertIn("users", data)
        self.assertGreaterEqual(len(data["users"]), 1)

        item = data["users"][0]
        self.assertIn("id", item)
        self.assertIn("email", item)
        self.assertIn("reason", item)
        self.assertIn("withdrawn_at", item)

    def test_non_admin_cannot_view_withdrawals(self) -> None:
        self.client.force_authenticate(user=self.normal_user)
        url = reverse("users:admin_withdrawal_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
