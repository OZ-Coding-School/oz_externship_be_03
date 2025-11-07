from __future__ import annotations

from typing import ClassVar

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.users.enums import Reason
from apps.users.models import User, Withdrawal


# ---------------------------------------------------------------------
# 어드민- 탈퇴 회원 리스트 조회 뷰 테스트
# ---------------------------------------------------------------------
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
        self.assertIn("results", data)
        self.assertGreaterEqual(len(data["results"]), 1)

        item = data["results"][0]
        self.assertIn("id", item)
        self.assertIn("email", item)
        self.assertIn("reason", item)
        self.assertIn("withdrawn_at", item)

    def test_non_admin_cannot_view_withdrawals(self) -> None:
        self.client.force_authenticate(user=self.normal_user)
        url = reverse("users:admin_withdrawal_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------
# 어드민- 탈퇴 회원 복구 뷰 테스트
# ---------------------------------------------------------------------
@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AdminUserRestoreViewTests(APITestCase):
    admin_id: ClassVar[int]
    user_with_withdrawal_inactive_id: ClassVar[int]
    user_without_withdrawal_inactive_id: ClassVar[int]
    user_with_withdrawal_active_id: ClassVar[int]

    url_name = "users:admin_user_restore"

    @classmethod
    def setUpTestData(cls) -> None:
        admin = User(
            email="admin@example.com",
            password="!",
            name="관리자",
            nickname="admin",
            birthday="1990-01-01",
            gender="f",
            phone_number="01000000000",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        u1 = User(  # 탈퇴내역 있음 + 비활성
            email="user1@example.com",
            password="!",
            name="유저1",
            nickname="user1",
            birthday="1990-01-01",
            gender="f",
            phone_number="01011111111",
            is_active=False,
        )
        u2 = User(  # 탈퇴내역 없음 + 비활성
            email="user2@example.com",
            password="!",
            name="유저2",
            nickname="user2",
            birthday="1992-02-02",
            gender="m",
            phone_number="01022222222",
            is_active=False,
        )
        u3 = User(  # 탈퇴내역 있음 + 활성
            email="user3@example.com",
            password="!",
            name="유저3",
            nickname="user3",
            birthday="1993-03-03",
            gender="m",
            phone_number="01033333333",
            is_active=True,
        )

        User.objects.bulk_create([admin, u1, u2, u3])

        cls.admin_id = User.objects.only("id").get(email="admin@example.com").id
        cls.user_with_withdrawal_inactive_id = User.objects.only("id").get(email="user1@example.com").id
        cls.user_without_withdrawal_inactive_id = User.objects.only("id").get(email="user2@example.com").id
        cls.user_with_withdrawal_active_id = User.objects.only("id").get(email="user3@example.com").id

        today = timezone.localdate()
        Withdrawal.objects.bulk_create(
            [
                Withdrawal(user_id=cls.user_with_withdrawal_inactive_id, due_date=today),
                Withdrawal(user_id=cls.user_with_withdrawal_active_id, due_date=today),
            ]
        )

    def setUp(self) -> None:
        admin = User.objects.get(pk=self.admin_id)
        self.client.force_authenticate(admin)

    def test_restore_success(self) -> None:
        """탈퇴 내역이 있는 비활성 유저 복구 → 200 & is_active=True & Withdrawal 삭제"""
        url = reverse(self.url_name, kwargs={"user_id": self.user_with_withdrawal_inactive_id})
        res = self.client.post(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.only("is_active").get(pk=self.user_with_withdrawal_inactive_id).is_active)
        self.assertFalse(Withdrawal.objects.filter(user_id=self.user_with_withdrawal_inactive_id).exists())

    def test_user_not_found(self) -> None:
        """대상 사용자가 없을 때 → 404"""
        url = reverse(self.url_name, kwargs={"user_id": 999999})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", res.data)

    def test_withdrawal_not_found(self) -> None:
        """탈퇴 내역이 없을 때 → 404"""
        url = reverse(self.url_name, kwargs={"user_id": self.user_without_withdrawal_inactive_id})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", res.data)

    def test_conflict_already_active(self) -> None:
        """이미 활성화된 계정일 때(탈퇴내역은 존재) → 409"""
        url = reverse(self.url_name, kwargs={"user_id": self.user_with_withdrawal_active_id})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("error", res.data)
