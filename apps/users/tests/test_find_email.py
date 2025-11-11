from __future__ import annotations

from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import PhoneVerificationPurpose
from apps.users.utils.phone_normalize import normalize_kr_phone
from apps.users.utils.verify_token import issue_verify_token

User = get_user_model()


class FindEmailTests(IsolatedRedisTestClient):
    """
    이메일 찾기 API 통합 테스트
    """

    def setUp(self) -> None:
        self.url = reverse("users:user_find_email")
        self.user = User.objects.create_user(
            email="me@example.com",
            password="pw123!!",
            nickname="me_nick",
            name="나",
            phone_number="01012345678",
            gender="M",
            birthday="1999-01-01",
            is_active=True,
        )

    def _issue_find_email_token(self, *, phone: str) -> str:
        return issue_verify_token(
            sub=phone,
            to=normalize_kr_phone(phone),
            purpose=PhoneVerificationPurpose.FIND_EMAIL,
        )

    def _headers(self, *, token: str) -> dict[str, str]:
        return {"HTTP_X_PHONE_VERIFY_TOKEN": token}

    def test_success_find_email_once(self) -> None:
        """
        1) 토큰 발급
        2) 헤더에 실어서 GET
        3) 이메일 마스킹되어서 반환
        """
        token = self._issue_find_email_token(phone=self.user.phone_number)

        resp = self.client.get(
            self.url,
            **self._headers(token=token),  # type: ignore[arg-type]
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["detail"], "이메일 찾기 완료.")
        self.assertIn("email", body["data"])
        # 마스킹이 되었는지 확인
        self.assertNotEqual(body["data"]["email"], self.user.email)
        self.assertTrue(body["data"]["email"].endswith("@example.com"))

    def test_permission_missing_token_returns_403(self) -> None:
        """
        토큰 미제공 → 퍼미션에서 403
        """
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_token_is_one_time_consumed(self) -> None:
        """
        같은 토큰 두 번 쓰면 두 번째는 퍼미션에서 403
        """
        token = self._issue_find_email_token(phone=self.user.phone_number)

        # 1회차: 성공
        r1 = self.client.get(
            self.url,
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)

        # 2회차: 같은 토큰 재사용 → verify_and_consume 에서 예외 401
        r2 = self.client.get(
            self.url,
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(r2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_not_found_returns_404(self) -> None:
        """
        토큰은 정상인데 DB에 없는 번호일 때
        """
        token = self._issue_find_email_token(phone="01099998888")

        resp = self.client.get(
            self.url,
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.json()["error"], "존재하지 않는 사용자입니다.")
