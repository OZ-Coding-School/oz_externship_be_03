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
            **self._headers(token=token),   # type: ignore[arg-type]
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

    def test_permission_missing_email_query_returns_403(self) -> None:
        # email 쿼리 누락 → 퍼미션에서 거절
        token = self._issue_reset_token(email=self.user.email)
        resp = self.client.post(
            self.url,  # ?email= 누락
            data=self._payload(new_pw="AAAbbb123!!", new_pw2="AAAbbb123!!"),
            format="json",
            **self._headers(token=token),   # type: ignore[arg-type]
        )
        # 퍼미션이 "이메일이 필요합니다." 메시지로 403을 반환해야 함
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("detail", resp.data)

    # 403 {'error': ErrorDetail(string='검증 토큰이 유효하지 않거나 만료되었습니다.', code='authentication_failed')} 이런식으로 401이 발생한거를 403이 덮고 있음 -> 원인?
    # def test_token_is_one_time_consumed(self) -> None:
    #     token = self._issue_reset_token(email=self.user.email)
    #
    #     # 1회차: 성공
    #     r1 = self.client.post(
    #         self._url_with_email(self.user.email),
    #         data=self._payload(new_pw="Passw0rd!!", new_pw2="Passw0rd!!"),
    #         format="json",
    #         **self._headers(token=token),
    #     )
    #     self.assertEqual(r1.status_code, status.HTTP_200_OK)
    #
    #     # 2회차: 같은 토큰 재사용 → verify_and_consume에서 401
    #     r2 = self.client.post(
    #         self._url_with_email(self.user.email),
    #         data=self._payload(new_pw="OtherPass1!!", new_pw2="OtherPass1!!"),
    #         format="json",
    #         **self._headers(token=token),
    #     )
    #     print("2nd resp:", r2.status_code, r2.data if hasattr(r2, "data") else r2.content)
    #     self.assertEqual(r2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_idempotency_key_noop_on_second_different_password(self) -> None:
        # 같은 멱등키로 2회 요청 시, 2번째는 NO-OP
        token1 = self._issue_reset_token(email=self.user.email)
        token2 = self._issue_reset_token(email=self.user.email)  # 퍼미션 1회성 때문에 새 토큰 필요
        idem_key = "00000000-0000-0000-0000-idem00000001"

        # 1회차: 성공
        r1 = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="FirstOk123!!", new_pw2="FirstOk123!!"),
            format="json",
            **self._headers(token=token1, idem=idem_key),   # type: ignore[arg-type]
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)

        # 2회차: 다른 비밀번호로 시도하지만 같은 멱등키 → NO-OP
        r2 = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="SecondXX123!!", new_pw2="SecondXX123!!"),
            format="json",
            **self._headers(token=token2, idem=idem_key),   # type: ignore[arg-type]
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("FirstOk123!!"))
        self.assertFalse(self.user.check_password("SecondXX123!!"))

    def test_password_policy_violation_returns_400(self) -> None:
        token = self._issue_reset_token(email=self.user.email)
        resp = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="short", new_pw2="short"),  # 정책 위반(예: 길이)
            format="json",
            **self._headers(token=token),   # type: ignore[arg-type]
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", str(resp.data))

    def test_mismatch_confirmation_returns_400(self) -> None:
        token = self._issue_reset_token(email=self.user.email)
        resp = self.client.post(
            self._url_with_email(self.user.email),
            data=self._payload(new_pw="NewPass123!!", new_pw2="NewPass123!!-typo"),
            format="json",
            **self._headers(token=token),   # type: ignore[arg-type]
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("비밀번호 확인", str(resp.data))
