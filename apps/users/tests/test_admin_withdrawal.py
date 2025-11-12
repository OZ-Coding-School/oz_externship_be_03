from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient, APITestCase

from apps.users.enums import Gender, Reason, Role
from apps.users.models import User, Withdrawal
from apps.users.services.admin_withdrawal_services import AdminWithdrawalService

# ============================================================
# 유틸
# ============================================================


def _uniq(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:4]}"


def _phone(seed: str) -> str:
    base = seed[:8].ljust(8, "0")
    return f"010{base}"


def create_user(**kwargs: Any) -> User:
    """
    테스트용 유저 생성
    """
    seed = uuid.uuid4().hex[:8]

    defaults: dict[str, Any] = dict(
        password="!",
        gender=Gender.MALE,
        birthday="1990-01-01",
        is_active=True,
        is_staff=False,
        is_superuser=False,
        nickname=_uniq("u"),
        name="테스트유저",
        phone_number=_phone(seed),
    )
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def create_admin(**kwargs: Any) -> User:
    seed = uuid.uuid4().hex[:8]
    return create_user(
        is_staff=True, is_superuser=True, name="관리자", phone_number=_phone(seed), nickname=_uniq("a"), **kwargs
    )


def create_withdrawal(user: User, **kwargs: Any) -> Withdrawal:
    defaults: dict[str, Any] = dict(
        reason=Reason.POOR_SERVICE_QUALITY.value,
        due_date=timezone.localdate(),
        reason_detail="기본 사유",
    )
    defaults.update(kwargs)
    return Withdrawal.objects.create(user=user, **defaults)


# ---------------------------------------------------------------------
# 어드민- 탈퇴 회원 리스트 조회 뷰 테스트
# ---------------------------------------------------------------------
class AdminWithdrawalListViewTestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        self.admin_user: User = create_admin(email="admin@example_list.com")

        self.normal_user: User = create_user(email="user_list@test.com")

        create_withdrawal(
            self.normal_user,
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

    w_inactive_id: ClassVar[int]
    w_active_id: ClassVar[int]

    url_name = "users:admin_withdrawal_restore"

    @classmethod
    def setUpTestData(cls) -> None:
        admin = create_admin(email="admin_restore@test.com")

        u1 = create_user(email="user1_restore@test.com", is_active=False)
        u2 = create_user(email="user2_restore@test.com", is_active=False)
        u3 = create_user(email="user3_restore@test.com", is_active=True)

        cls.admin_id = admin.id
        cls.user_with_withdrawal_inactive_id = u1.id
        cls.user_without_withdrawal_inactive_id = u2.id
        cls.user_with_withdrawal_active_id = u3.id

        today = timezone.localdate()
        w1 = Withdrawal.objects.create(user_id=u1.id, due_date=today)
        w3 = Withdrawal.objects.create(user_id=u3.id, due_date=today)
        cls.w_inactive_id = w1.id
        cls.w_active_id = w3.id

    def setUp(self) -> None:
        admin = User.objects.get(pk=self.admin_id)
        self.client.force_authenticate(admin)

    def test_restore_success(self) -> None:
        """탈퇴 내역이 있는 비활성 유저 복구 → 200 & is_active=True & Withdrawal 삭제"""
        url = reverse(self.url_name, kwargs={"withdrawal_id": self.w_inactive_id})
        res = self.client.post(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.only("is_active").get(pk=self.user_with_withdrawal_inactive_id).is_active)
        self.assertFalse(Withdrawal.objects.filter(user_id=self.user_with_withdrawal_inactive_id).exists())

    def test_user_not_found(self) -> None:
        """대상 사용자가 없을 때 → 404"""
        url = reverse(self.url_name, kwargs={"withdrawal_id": 999_999})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", res.data)

    def test_withdrawal_not_found(self) -> None:
        """탈퇴 내역이 없을 때 → 404"""
        url = reverse(self.url_name, kwargs={"withdrawal_id": 123_456_789})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", res.data)

    def test_conflict_already_active(self) -> None:
        """이미 활성화된 계정일 때(탈퇴내역은 존재) → 409"""
        url = reverse(self.url_name, kwargs={"withdrawal_id": self.w_active_id})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("error", res.data)


# ---------------------------------------------------------------------
# 어드민- 탈퇴 회원 상세 조회 뷰 테스트
# ---------------------------------------------------------------------
class TestAdminWithdrawalDetailAPI(APITestCase):

    admin_user: ClassVar[User]
    withdrawn_user: ClassVar[User]
    normal_active_user: ClassVar[User]
    withdrawal: ClassVar[Withdrawal]

    @classmethod
    def setUpTestData(cls) -> None:
        # --- 관리자 생성 ---
        s_admin = _uniq("a")
        cls.admin_user = create_admin(
            email=f"{s_admin}@example.com",
        )

        # --- 탈퇴(비활성) 유저 생성 ---
        s_with = _uniq("w")
        cls.withdrawn_user = create_user(
            email=f"{s_with}@example.com",
            password="user1234!",
            nickname=f"{s_with}",
            name="홍길동",
            phone_number=_phone(uuid.uuid4().hex[:8]),
            gender=Gender.MALE,
            birthday="1995-05-05",
            is_active=False,
        )

        # --- 탈퇴 내역 생성 ---
        cls.withdrawal = create_withdrawal(
            cls.withdrawn_user,
            reason_detail="응답 속도가 느림",
        )

        # --- 탈퇴 내역 없는 일반 유저 ---
        s_norm = _uniq("n")
        cls.normal_active_user = create_user(
            email=f"{s_norm}@example.com",
            nickname=f"{s_norm}",
            name="김아무개",
            phone_number=_phone(uuid.uuid4().hex[:8]),
            gender=Gender.MALE,
            birthday="1996-06-06",
            is_active=True,
        )

    # ---------------------------
    # 성공: 200
    # ---------------------------
    def test_withdrawal_detail_success(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("users:admin_withdrawal_detail", kwargs={"withdrawal_id": self.withdrawal.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["detail"], "탈퇴 내역 상세 조회에 성공하였습니다.")

        user_data = res.data["data"]["user"]
        withdrawal_data = res.data["data"]["withdrawal"]

        self.assertEqual(user_data["id"], self.withdrawn_user.id)
        self.assertEqual(user_data["email"], self.withdrawn_user.email)
        self.assertEqual(user_data["name"], self.withdrawn_user.name)
        self.assertIn(str(Role.USER), {user_data.get("role"), str(user_data.get("role"))})

        self.assertIn("reason", withdrawal_data)
        self.assertEqual(withdrawal_data.get("reason"), Reason.POOR_SERVICE_QUALITY.value)

    # ---------------------------
    # 대상 없음: 404
    # ---------------------------
    def test_withdrawal_detail_not_found(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("users:admin_withdrawal_detail", kwargs={"withdrawal_id": 999_999})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", res.data)
        self.assertIn("탈퇴 이력이 없습니다.", res.data["error"])

    # ---------------------------
    # 권한 없음: 403
    # ---------------------------
    def test_withdrawal_detail_permission_denied(self) -> None:
        self.client.force_authenticate(user=self.withdrawn_user)
        url = reverse("users:admin_withdrawal_detail", kwargs={"withdrawal_id": self.withdrawn_user.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------
# 어드민- 탈퇴 회원 상세 조회 서비스 테스트
# ---------------------------------------------------------------------
class AdminWithdrawalServiceTests(TestCase):
    def test_user_not_found_raises_not_found(self) -> None:
        # 존재하지 않는 탈퇴 요청 ID
        with self.assertRaises(NotFound):
            AdminWithdrawalService.get_withdrawal_detail(withdrawal_id=999_999)
