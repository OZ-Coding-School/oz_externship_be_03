from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import Gender, Reason

User = get_user_model()


def aware(dt: datetime) -> datetime:
    """현재 타임존으로 aware datetime 생성"""
    return timezone.make_aware(dt, timezone.get_current_timezone())


class SignupTrendsAPITests(IsolatedRedisTestClient):
    def setUp(self) -> None:
        self.url = reverse("users:signup_trends")
        self.admin = User.objects.create_superuser(
            name="관리자",
            email="admin@example.com",
            password="pw1234!!",
            nickname="admin",
            phone_number="01011112223",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )
        self.user = User.objects.create_user(
            name="사용자",
            email="user@example.com",
            password="pw1234!!",
            nickname="me_nick",
            phone_number="01011112222",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )

    def _mk_signups(self, y: int, m: int, d: int = 1, n: int = 1, *, is_active: bool = True) -> None:
        """
        created_at = y-m-d 로 User n명 생성 (회원가입 추세 집계용)
        """
        dt = aware(datetime(y, m, d, 12, 0, 0))  # 정오 + aware (경계 안전)
        suffix = uuid4().hex[:6]

        for i in range(n):
            u = User.objects.create_user(
                email=f"email{suffix}-{i}@example.com",
                password="testpwd",
                is_active=is_active,
                name=f"테스트",
                nickname=f"유저{suffix}{i}",
                phone_number=f"0101{i}{suffix}",
                birthday=date(1990, 1, 1),
                gender=Gender.MALE,
            )
            # auto_now_add 무시하고 DB에서 생성시각 덮어쓰기
            User.objects.filter(pk=u.pk).update(created_at=dt)

    def test_auth_required(self) -> None:
        # 비로그인 → 401
        resp = self.client.get(self.url, {"interval": "month"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # 일반유저 → 403
        self.client.force_authenticate(self.user)
        resp = self.client.get(self.url, {"interval": "month"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("django.utils.timezone.localdate", return_value=date(2025, 11, 10))
    def test_invalid_interval_returns_400(self, _mock_today: Any) -> None:
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.url, {"interval": "weekly"})  # 잘못된 값
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        self.assertIn("error", body)

    @patch("django.utils.timezone.localdate", return_value=date(2025, 11, 10))
    def test_month_aggregation_includes_current_month_until_today(self, _mock_today: Any) -> None:
        """
        today=2025-11-10 기준:
        - window: from=2024-12-01, to=2025-11-10
        - 라벨: 2024-12 .. 2025-11
        """
        self.client.force_authenticate(self.admin)

        # 샘플 데이터: 2024-12(1), 2025-02(2), 2025-11(3; 진행중인 달)
        self._mk_signups(2024, 12, 15, n=1)
        self._mk_signups(2025, 2, 1, n=2)
        self._mk_signups(2025, 11, 9, n=3)  # 오늘(10일) 이전

        resp = self.client.get(self.url, {"interval": "month"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()

        data = body["data"]
        self.assertEqual(data["interval"], "month")
        self.assertEqual(data["from"], "2024-12-01")
        self.assertEqual(data["to"], "2025-11-10")

        items = data["items"]
        self.assertEqual(len(items), 12)
        expected_periods = [
            "2024-12",
            "2025-01",
            "2025-02",
            "2025-03",
            "2025-04",
            "2025-05",
            "2025-06",
            "2025-07",
            "2025-08",
            "2025-09",
            "2025-10",
            "2025-11",
        ]
        self.assertEqual([i["period"] for i in items], expected_periods)

        items_map = {i["period"]: i["count"] for i in items}
        self.assertEqual(items_map["2024-12"], 1)
        self.assertEqual(items_map["2025-02"], 2)
        self.assertEqual(items_map["2025-11"], 3 + 2)
        self.assertEqual(items_map["2025-01"], 0)
        self.assertEqual(items_map["2025-03"], 0)

        self.assertEqual(data["total_signups"], 6 + 2)

    @patch("django.utils.timezone.localdate", return_value=date(2025, 11, 10))
    def test_year_aggregation_last_5_years_includes_today(self, _mock_today: Any) -> None:
        """
        today=2025-11-10 기준:
        - window: from=2021-01-01, to=2025-11-10
        - periods: 2021..2025
        """
        self.client.force_authenticate(self.admin)

        # 샘플 데이터: 2021(2), 2023(3), 2025(4)
        self._mk_signups(2021, 1, 1, n=2)
        self._mk_signups(2023, 6, 1, n=3)
        self._mk_signups(2025, 10, 1, n=4)

        resp = self.client.get(self.url, {"interval": "year"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]

        self.assertEqual(data["interval"], "year")
        self.assertEqual(data["from"], "2021-01-01")
        self.assertEqual(data["to"], "2025-11-10")

        items = data["items"]
        self.assertEqual(len(items), 5)
        items_map = {i["period"]: i["count"] for i in items}
        self.assertEqual(items_map["2021"], 2)
        self.assertEqual(items_map["2023"], 3)
        self.assertEqual(items_map["2025"], 4 + 2)
        self.assertEqual(items_map["2022"], 0)
        self.assertEqual(items_map["2024"], 0)

        self.assertEqual(data["total_signups"], 2 + 3 + 4 + 2)
