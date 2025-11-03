from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import EmailVerificationPurpose
from apps.users.utils.verify_token import issue_verify_token

User = get_user_model()


class PasswordResetIntegrationTests(IsolatedRedisTestClient):
    """
    /api/v1/users/reset-password 통합 테스트
    - 퍼미션(EmailVerifiedPermission): 헤더/쿼리파라미터 검사 및 1회성 소비
    - verify_token: 발급/검증/소비(재사용 차단)
    - 서비스(reset_password): 멱등성, 비밀번호 정책, 불일치 검증
    """

    def setUp(self) -> None:
        self.url = reverse("users:user_reset_password")
        self.user = User.objects.create_user(
            email="me@example.com",
            password="Oldpw123!!",
            nickname="me_nick",
            name="나",
            phone_number="01012345678",
            gender="M",
            birthday="1999-01-01",
            is_active=True,
        )

    def _issue_reset_token(self, *, email: str) -> str:
        # 이메일 기반 sub 고정
        return issue_verify_token(
            sub=email,
            to=email,
            purpose=EmailVerificationPurpose.RESET_PASSWORD,
        )

    def _payload(self, *, new_pw: str, new_pw2: str) -> dict[str, Any]:
        return {"new_password": new_pw, "new_password_confirm": new_pw2}

    def _headers(self, *, token: str, idem: str | None = None) -> dict[str, str]:
        headers = {"HTTP_X_EMAIL_VERIFY_TOKEN": token}
        if idem:
            headers["HTTP_IDEMPOTENCY_KEY"] = idem
        return headers

    def _url_with_email(self, email: str) -> str:
        return f"{self.url}?email={email}"

    def test_success_password_reset_once(self) -> None:
        token = self._issue_reset_token(email=self.user.email)
        resp = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="NewPass123!!", new_pw2="NewPass123!!"),
            format="json",
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass123!!"))

    def test_permission_missing_token_returns_403(self) -> None:
        # 토큰 미제공 → 퍼미션 단계에서 거절(403)
        resp = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="AAAbbb123!!", new_pw2="AAAbbb123!!"),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("detail", resp.data)

    def test_token_is_one_time_consumed(self) -> None:
        token = self._issue_reset_token(email=self.user.email)

        # 1회차: 성공
        r1 = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="Passw0rd!!", new_pw2="Passw0rd!!"),
            format="json",
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)

        # 2회차: 같은 토큰 재사용 → verify_and_consume에서 401 → permission에서 403
        # DRF 설계 구조상 permission check 중일 때 예외가 발생하면 무조건 403으로 처리하기 때문에 401로 처리 불가
        r2 = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="OtherPass1!!", new_pw2="OtherPass1!!"),
            format="json",
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

    def test_password_policy_violation_returns_400(self) -> None:
        token = self._issue_reset_token(email=self.user.email)
        resp = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="short", new_pw2="short"),  # 정책 위반(예: 길이)
            format="json",
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", str(resp.data))

    def test_mismatch_confirmation_returns_400(self) -> None:
        token = self._issue_reset_token(email=self.user.email)
        resp = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="NewPass123!!", new_pw2="NewPass123!!-typo"),
            format="json",
            **self._headers(token=token),  # type: ignore[arg-type]
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("비밀번호 확인", str(resp.data))
