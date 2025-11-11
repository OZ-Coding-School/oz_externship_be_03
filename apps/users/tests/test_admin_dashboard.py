from __future__ import annotations

from datetime import date, datetime, timedelta
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
    base_url: str

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.base_url = reverse("users:admin_withdrawal_list_by_reason")

    def test_success(self) -> None:
        """정상 요청(200) + 12개월 고정 + 총합 3건"""
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.base_url, {"reason": self.target_reason})
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        data = r.data["data"]
        self.assertEqual(data["interval"], "month")
        self.assertEqual(len(data["items"]), 12)
        self.assertEqual(sum(i["count"] for i in data["items"]), 3)

    def test_invalid_reason(self) -> None:
        """유효하지 않은 reason → 400"""
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.base_url, {"reason": "INVALID"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("유효하지 않은 사유입니다.", r.data["error"])

    def test_forbidden(self) -> None:
        """staff 권한 없으면 → 403"""
        self.client.force_authenticate(self.normal_user)
        r = self.client.get(self.base_url, {"reason": self.target_reason})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthorized(self) -> None:
        """인증 없으면 → 401"""
        r = self.client.get(self.base_url, {"reason": self.target_reason})
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_zero_filled(self) -> None:
        """데이터 없는 월은 count=0으로 채워져야 함"""
        self.client.force_authenticate(self.admin)
        items = self.client.get(self.base_url, {"reason": self.target_reason}).data["data"]["items"]
        self.assertTrue(any(i["count"] == 0 for i in items))


# ---------------------------------------------------------
# 어드민 - 대시보드 회원 탈퇴 사유 추적 서비스 테스트
# ---------------------------------------------------------
class TestAdminDashboardStatsService(BaseDashboardTest, TestCase):
    def test_month(self) -> None:
        """최근 12개월 월간 통계: 총합 3, 아이템 12개"""
        r = AdminDashboardStatsService.get_trends("month", reason=self.target_reason)
        self.assertEqual(r.total_withdrawals, 3)
        self.assertEqual(len(r.items), 12)

    def test_year(self) -> None:
        """최근 5년 연간 통계: 총합 3, 아이템 5개"""
        r = AdminDashboardStatsService.get_trends("year", reason=self.target_reason)
        self.assertEqual(r.total_withdrawals, 3)
        self.assertEqual(len(r.items), 5)

    def test_month_no_reason(self) -> None:
        """reason=None(전체 집계)도 총합 3 이어야 함"""
        r = AdminDashboardStatsService.get_trends("month")
        self.assertEqual(r.total_withdrawals, 3)

    def test_year_interval_coverage(self) -> None:
        """
        최근 5년 중 '올해'에만 3건이며 나머지 연도는 0건이어야 함
        """
        r = AdminDashboardStatsService.get_trends("year")
        self.assertEqual(len(r.items), 5)
        self.assertEqual(r.items[-1].count, 3)
        for item in r.items[:-1]:
            self.assertEqual(item.count, 0)


# ---------------------------------------------------------
# 어드민 - 대시보드 회원 탈퇴 사유 분포(전체 기간) 뷰 테스트
# ---------------------------------------------------------
class TestAdminWithdrawalReasonStatsAllTimeView(BaseDashboardTest, APITestCase):
    base_url: str

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.base_url = reverse("users:admin_withdrawal_reason_distribution")

        today = cls.today
        due = today + timedelta(days=DELETE_GRACE_DAYS)

        extra: List[Withdrawal] = []
        extra.append(
            Withdrawal(
                user=cls.normal_user,
                reason=Reason.POOR_SERVICE_QUALITY.value,
                reason_detail="품질 불만",
                due_date=due,
                created_at=datetime(today.year, today.month, 5, 10, 0),
            )
        )
        extra.append(
            Withdrawal(
                user=cls.normal_user,
                reason=Reason.PRIVACY_CONCERNS.value,
                reason_detail=" 보안 우려",
                due_date=due,
                created_at=datetime(today.year, max(1, today.month - 2), 20, 11, 0),
            )
        )

        two_years_ago = today.replace(year=today.year - 2)
        extra.append(
            Withdrawal(
                user=cls.normal_user,
                reason=Reason.LACK_OF_INTEREST.value,
                reason_detail="관심 하락",
                due_date=due,
                created_at=datetime(two_years_ago.year, two_years_ago.month, 10, 9, 0),
            )
        )
        Withdrawal.objects.bulk_create(extra)

    # ---------------------------
    # 성공: 200
    # ---------------------------
    def test_success_all_time(self) -> None:
        """정상 요청(200) + interval=all_time + 전체 합계/아이템 유효성"""
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.base_url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        data = r.data["data"]
        self.assertEqual(data["interval"], "all_time")
        self.assertIn("from_date", data)
        self.assertIn("to_date", data)
        self.assertIn("items", data)

        items = data["items"]
        self.assertEqual(len(items), len(Reason))

        self.assertEqual(
            data["total_withdrawals"],
            sum(i["count"] for i in items),
        )

        sample = items[0]
        self.assertIn("reason_code", sample)
        self.assertIn("reason_label", sample)
        self.assertIn("count", sample)
        self.assertIn("percentage", sample)

    # ---------------------------
    # 날짜 필터: 200
    # ---------------------------
    def test_date_range_filters(self) -> None:
        """date_from/date_to로 범위 제한 시, 범위 밖 데이터가 제외되는지 확인"""
        self.client.force_authenticate(self.admin)

        # 범위를 '작년 1월 1일 ~ 오늘'로 설정
        today = self.today
        date_from = date(today.year - 1, 1, 1).isoformat()
        date_to = today.isoformat()

        r = self.client.get(self.base_url, {"date_from": date_from, "date_to": date_to})
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        data = r.data["data"]
        items = data["items"]
        total = data["total_withdrawals"]

        self.assertEqual(total, 6)
        self.assertEqual(total, sum(i["count"] for i in items))

        # 퍼센트는 total>0이면 0~100 사이
        for i in items:
            self.assertGreaterEqual(i["percentage"], 0.0)
            self.assertLessEqual(i["percentage"], 100.0)

    # ---------------------------
    # 잘못된 날짜 형식: 400
    # ---------------------------
    def test_invalid_date_format(self) -> None:
        """YYYY-MM-DD 형식이 아니면 400"""
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.base_url, {"date_from": "2025/01/01"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("날짜 형식", r.data["error"])

    # ---------------------------
    # 미래 날짜 포함: 400
    # ---------------------------
    def test_future_date_not_allowed(self) -> None:
        """date_to가 오늘 기준 미래면 400"""
        self.client.force_authenticate(self.admin)

        today = self.today
        date_from = date(today.year - 1, 1, 1).isoformat()
        date_to = (today + timedelta(days=1)).isoformat()
        r = self.client.get(self.base_url, {"date_from": date_from, "date_to": date_to})

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("미래 날짜는 허용되지 않습니다.", r.data["error"])

    # ---------------------------
    # 시작일 > 종료일: 400
    # ---------------------------
    def test_date_range_reversed(self) -> None:
        """date_from이 date_to보다 이후면 400"""
        self.client.force_authenticate(self.admin)

        today = self.today
        date_from = today.isoformat()
        date_to = date(today.year - 1, 1, 1).isoformat()
        r = self.client.get(self.base_url, {"date_from": date_from, "date_to": date_to})

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("시작일은 종료일보다 이후일 수 없습니다.", r.data["error"])

    # ---------------------------
    # 권한 없음: 403
    # ---------------------------
    def test_forbidden(self) -> None:
        """staff 권한 없으면 → 403"""
        self.client.force_authenticate(self.normal_user)
        r = self.client.get(self.base_url)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    # ---------------------------
    # 인증 없음: 401
    # ---------------------------
    def test_unauthorized(self) -> None:
        """인증 없으면 → 401"""
        r = self.client.get(self.base_url)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
