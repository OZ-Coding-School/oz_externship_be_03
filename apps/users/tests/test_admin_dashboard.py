from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.enums import Reason
from apps.users.models import User, Withdrawal
from apps.users.services.admin_dashboard_services import AdminDashboardStatsService

DELETE_GRACE_DAYS = 14


# ---------------------------------------------------------
# 공통 클래스
# ---------------------------------------------------------
class BaseDashboardTest:
    admin: User
    normal_user: User
    target_reason: str
    url: str
    today = timezone.localdate()

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin = User.objects.create_user(
            email="admin@example.com",
            password="1234",
            name="관리자",
            nickname="admin",
            gender="male",
            phone_number="01000000000",
            birthday="1990-01-01",
            is_active=True,
            is_staff=True,
        )

        cls.normal_user = User.objects.create_user(
            email="normal@example.com",
            password="1234",
            name="일반유저",
            nickname="normal",
            gender="male",
            phone_number="01011112222",
            birthday="1995-01-01",
            is_active=True,
        )

        cls.target_reason = Reason.LACK_OF_CONTENT.value

        due_date = cls.today + timedelta(days=DELETE_GRACE_DAYS)

        withdrawals: List[Withdrawal] = []
        for offset in [0, 1, 5]:
            dt = cls.today - timedelta(days=30 * offset)
            withdrawals.append(
                Withdrawal(
                    user=cls.normal_user,
                    reason=cls.target_reason,
                    reason_detail="컨텐츠 없음",
                    due_date=due_date,
                    created_at=datetime(dt.year, dt.month, 15, 14, 0),
                )
            )

        Withdrawal.objects.bulk_create(withdrawals)


# ---------------------------------------------------------
# 어드민 - 대시보드 회원 탈퇴 사유 추적 뷰 테스트
# ---------------------------------------------------------
class TestAdminWithdrawalReasonStatsView(BaseDashboardTest, APITestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.url = reverse(
            "users:admin_withdrawal_list_by_reason",
            kwargs={"reason": cls.target_reason},
        )

    def test_success(self) -> None:
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url)

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data["data"]

        self.assertEqual(data["interval"], "month")
        self.assertEqual(len(data["items"]), 12)
        self.assertEqual(sum(i["count"] for i in data["items"]), 3)

    def test_invalid_reason(self) -> None:
        """
        유효하지 않은 reason → 400 에러 반환
        """
        self.client.force_authenticate(self.admin)
        url = reverse(
            "users:admin_withdrawal_list_by_reason",
            kwargs={"reason": "INVALID"},
        )
        r = self.client.get(url)

        self.assertEqual(r.status_code, 400)
        self.assertIn("유효하지 않은 사유입니다.", r.data["error"])

    def test_forbidden(self) -> None:
        """
        staff 권한이 없으면 → 403 반환
        """
        self.client.force_authenticate(self.normal_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_unauthorized(self) -> None:
        """
        인증 없이 접근 → 401 반환
        """
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 401)

    def test_zero_filled(self) -> None:
        """
        12개월 중 데이터가 없는 달은 count=0 으로 채워져야 함
        """
        self.client.force_authenticate(self.admin)
        items = self.client.get(self.url).data["data"]["items"]
        self.assertTrue(any(i["count"] == 0 for i in items))


# ---------------------------------------------------------
# 어드민 - 대시보드 회원 탈퇴 사유 추적 서비스 테스트
# ---------------------------------------------------------
class TestAdminDashboardStatsService(BaseDashboardTest, TestCase):

    def test_month(self) -> None:
        """
        최근 12개월 월간 통계 테스트
        """
        r = AdminDashboardStatsService.get_trends("month", reason=self.target_reason)
        self.assertEqual(r.total, 3)
        self.assertEqual(len(r.items), 12)

    def test_year(self) -> None:
        """
        최근 5년 연간 통계 테스트
        """
        r = AdminDashboardStatsService.get_trends("year", reason=self.target_reason)
        self.assertEqual(r.total, 3)
        self.assertEqual(len(r.items), 5)

    def test_month_no_reason(self) -> None:
        """
        reason=None (전체 집계)
        """
        r = AdminDashboardStatsService.get_trends("month")
        self.assertEqual(r.total, 3)

    def test_year_interval_coverage(self) -> None:
        """
        - 최근 5년 중 올해(period[-1])에만 3건 존재해야 함
        - 나머지 연도는 0건이어야 함
        """
        r = AdminDashboardStatsService.get_trends("year")

        self.assertEqual(len(r.items), 5)
        self.assertEqual(r.items[-1].count, 3)

        for item in r.items[:-1]:
            self.assertEqual(item.count, 0)
