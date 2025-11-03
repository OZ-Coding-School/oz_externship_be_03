from __future__ import annotations

import json
import re
from typing import Any, Dict, Protocol, cast, runtime_checkable
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import path, reverse
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient, APITestCase
from rest_framework.views import APIView

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import EmailVerificationPurpose
from apps.users.permissions import EmailVerifiedPermission
from apps.users.services import email_verification_services as svc


# ========== 공통 타입 유틸 ==========
@runtime_checkable
class RespLike(Protocol):
    status_code: int
    content: bytes


# ============================================================================
# 1) 이메일 인증/검증 뷰 테스트 (DRF APIClient 사용)
# ============================================================================
class TestEmailVerificationViews(IsolatedRedisTestClient):
    """각 목적(SIGNUP/RESET_PASSWORD/RESTORE_USER/CHANGE_EMAIL)별 뷰 동작 검증"""

    def setUp(self) -> None:
        super().setUp()
        self.client: APIClient = APIClient()
        self.email: str = "example@example.com"
        self.send_payload: dict[str, str] = {"email": self.email}
        self.confirm_payload: dict[str, str] = {
            "email": self.email,
            "request_id": "SID12345",
            "verification_code": "123456",
        }

    def _post_json(self, url: str, payload: dict[str, Any]) -> RespLike:
        """JSON POST 헬퍼"""
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    # --- 회원가입 ---
    @patch("apps.users.views.email_verification_views.svc.email_send_code")
    def test_signup_send_code_success(self, mock_send: Mock) -> None:
        mock_send.return_value = {
            "request_id": "SID12345",
            "expires_in": 180,
            "cooldown": 30,
            "max_attempts": 5,
        }
        url = reverse("users:email_signup_send_code")

        resp = self._post_json(url, self.send_payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["detail"], "인증코드를 발송했습니다.")
        self.assertEqual(body["data"]["request_id"], "SID12345")

        mock_send.assert_called_once_with(
            purpose=EmailVerificationPurpose.SIGNUP,
            email=self.email,
        )

    @patch("apps.users.views.email_verification_views.svc.email_confirm_code")
    def test_signup_confirm_code_success(self, mock_confirm: Mock) -> None:
        mock_confirm.return_value = {"verify_token": "VTOK-123", "expires_in": 300}
        url = reverse("users:email_signup_confirm_code")

        resp = self._post_json(url, self.confirm_payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["detail"], "인증이 완료되었습니다.")
        self.assertEqual(body["data"]["verify_token"], "VTOK-123")
        self.assertEqual(body["data"]["expires_in"], 300)

        mock_confirm.assert_called_once_with(
            purpose=EmailVerificationPurpose.SIGNUP,
            email=self.email,
            verification_code="123456",
            request_id="SID12345",
        )

    # --- 비번 재설정 (비번 찾기) ---
    @patch("apps.users.views.email_verification_views.svc.email_send_code")
    def test_reset_password_send_code_success(self, mock_send: Mock) -> None:
        mock_send.return_value = {
            "request_id": "SID12345",
            "expires_in": 180,
            "cooldown": 30,
            "max_attempts": 5,
        }
        url = reverse("users:email_reset_password_send_code")

        resp = self._post_json(url, self.send_payload)
        self.assertEqual(resp.status_code, 200, resp.content)

        mock_send.assert_called_once_with(
            purpose=EmailVerificationPurpose.RESET_PASSWORD,
            email=self.email,
        )

    @patch("apps.users.views.email_verification_views.svc.email_confirm_code")
    def test_reset_password_confirm_code_success(self, mock_confirm: Mock) -> None:
        mock_confirm.return_value = {"verify_token": "VTOK-123", "expires_in": 300}
        url = reverse("users:email_reset_password_confirm_code")

        resp = self._post_json(url, self.confirm_payload)
        self.assertEqual(resp.status_code, 200, resp.content)

        mock_confirm.assert_called_once_with(
            purpose=EmailVerificationPurpose.RESET_PASSWORD,
            email=self.email,
            verification_code="123456",
            request_id="SID12345",
        )

    # --- 탈퇴 계정 복구 ---
    @patch("apps.users.views.email_verification_views.svc.email_send_code")
    def test_restore_user_send_code_success(self, mock_send: Mock) -> None:
        mock_send.return_value = {
            "request_id": "SID12345",
            "expires_in": 180,
            "cooldown": 30,
            "max_attempts": 5,
        }
        url = reverse("users:email_restore_user_send_code")

        resp = self._post_json(url, self.send_payload)
        self.assertEqual(resp.status_code, 200, resp.content)

        mock_send.assert_called_once_with(
            purpose=EmailVerificationPurpose.RESTORE_USER,
            email=self.email,
        )

    @patch("apps.users.views.email_verification_views.svc.email_confirm_code")
    def test_restore_user_confirm_code_success(self, mock_confirm: Mock) -> None:
        mock_confirm.return_value = {"verify_token": "VTOK-123", "expires_in": 300}
        url = reverse("users:email_restore_user_confirm_code")

        resp = self._post_json(url, self.confirm_payload)
        self.assertEqual(resp.status_code, 200, resp.content)

        mock_confirm.assert_called_once_with(
            purpose=EmailVerificationPurpose.RESTORE_USER,
            email=self.email,
            verification_code="123456",
            request_id="SID12345",
        )

    # --- 이메일 변경 (인증 필요) ---
    @patch("apps.users.views.email_verification_views.svc.email_send_code")
    def test_change_email_send_code_requires_auth_then_success(self, mock_send: Mock) -> None:
        url = reverse("users:email_change_email_send_code")

        unauth = self._post_json(url, self.send_payload)
        self.assertIn(unauth.status_code, (401, 403))

        user = get_user_model().objects.create_user(
            email="user1@example.com",
            password="pass1234!",
            nickname="user1",
            birthday="1990-01-01",
            gender="M",
        )
        self.client.force_authenticate(user=user)

        mock_send.return_value = {
            "request_id": "SID12345",
            "expires_in": 180,
            "cooldown": 30,
            "max_attempts": 5,
        }
        resp = self._post_json(url, self.send_payload)
        self.assertEqual(resp.status_code, 200, resp.content)

        mock_send.assert_called_once_with(
            purpose=EmailVerificationPurpose.CHANGE_EMAIL,
            email=self.email,
        )

    @patch("apps.users.views.email_verification_views.svc.email_confirm_code")
    def test_change_email_confirm_code_requires_auth_then_success(self, mock_confirm: Mock) -> None:
        url = reverse("users:email_change_email_confirm_code")

        unauth = self._post_json(url, self.confirm_payload)
        self.assertIn(unauth.status_code, (401, 403))

        user = get_user_model().objects.create_user(
            email="user2@example.com",
            password="pass1234!",
            nickname="user2",
            birthday="1990-01-01",
            gender="M",
        )
        self.client.force_authenticate(user=user)

        mock_confirm.return_value = {"verify_token": "VTOK-123", "expires_in": 300}
        resp = self._post_json(url, self.confirm_payload)
        self.assertEqual(resp.status_code, 200, resp.content)

        mock_confirm.assert_called_once_with(
            purpose=EmailVerificationPurpose.CHANGE_EMAIL,
            email=self.email,
            verification_code="123456",
            request_id="SID12345",
        )


# ============================================================================
# 2) 이메일 인증/검증 서비스 테스트 (send/confirm 로직)
# ============================================================================
LOC_MEM_EMAIL = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
CODE_RE = re.compile(r"인증코드:\s*(\d{6})")


def _extract_code_from_outbox() -> str:
    """locmem outbox에서 6자리 코드 추출"""
    assert len(mail.outbox) == 1, f"outbox={mail.outbox}"
    body: str = cast(str, mail.outbox[0].body)
    m = CODE_RE.search(body)
    assert m, f"본문에서 6자리 인증코드를 찾지 못함: {body!r}"
    return m.group(1)


class TestEmailVerificationServices(IsolatedRedisTestClient):
    """유틸/발송/확인 전 구간 커버리지 확보"""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        mail.outbox.clear()

    def tearDown(self) -> None:
        cache.clear()
        mail.outbox.clear()
        super().tearDown()

    # --- 유틸 함수 ---
    def test_utils_all(self) -> None:
        assert svc._purpose_str(EmailVerificationPurpose.SIGNUP) == "signup"
        assert svc._purpose_str(EmailVerificationPurpose.RESET_PASSWORD) == "reset_password"
        assert svc._purpose_whitelist(EmailVerificationPurpose.SIGNUP) is True
        assert svc._purpose_whitelist(EmailVerificationPurpose.RESTORE_USER) is True
        assert svc._purpose_whitelist(EmailVerificationPurpose.CHANGE_EMAIL) is True
        assert svc._purpose_whitelist("invalid") is False

        assert svc._normalize_email("A@Example.COM") == "A@example.com"

        email = "u@example.com"
        rid = "RID123"
        assert (
            svc._pending_key(email, EmailVerificationPurpose.SIGNUP, rid)
            == f"verify:email:pending:{email}:signup:{rid}"
        )
        assert svc._lock_key(email, EmailVerificationPurpose.SIGNUP) == f"verify:email:lock:{email}:signup"
        assert svc._fail_key(email, EmailVerificationPurpose.SIGNUP) == f"verify:email:failcnt:{email}:signup"
        assert svc._rate_key(email) == f"ratelimit:email:send:{email}"
        assert svc._global_fail_key(email) == f"verify:email:failcnt:global:{email}"
        assert svc._global_lock_key(email) == f"verify:email:lock:global:{email}"

        c1 = svc._generate_code()
        c2 = svc._generate_code()
        assert len(c1) == 6 and c1.isdigit()
        assert len(c2) == 6 and c2.isdigit()

        key = "test:incr:key"
        cache.delete(key)
        v1 = svc._safe_incr(key, ttl=10)
        v2 = svc._safe_incr(key, ttl=10)
        assert (v1, v2) == (1, 2)

    # --- 코드 발송 ---
    @override_settings(**LOC_MEM_EMAIL)
    def test_send_code_success_and_template_fields(self) -> None:
        with (
            patch.object(svc, "RESEND_COOLDOWN_SECONDS", 60, create=True),
            patch.object(svc, "ONE_TIME_TTL_SECONDS", 600, create=True),
            patch.object(svc, "MAX_FAIL_ATTEMPTS", 5, create=True),
            patch.object(svc, "DEFAULT_FROM_EMAIL", "no-reply@example.com", create=True),
        ):
            resp = svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="USER@Example.COM")
            assert isinstance(resp, dict), resp
            request_id = resp["request_id"]

            assert len(mail.outbox) == 1
            msg = mail.outbox[0]
            assert msg.from_email == "no-reply@example.com"
            assert msg.to == ["USER@example.com"]
            body = msg.body
            assert "요청 목적: signup" in body
            assert "유효시간: 600초" in body
            code = _extract_code_from_outbox()

            pending_key = svc._pending_key("USER@example.com", EmailVerificationPurpose.SIGNUP, request_id)
            assert cache.get(pending_key) == code
            assert cache.get(svc._rate_key("USER@example.com")) is not None

    def test_send_code_invalid_purpose_returns_400(self) -> None:
        resp = svc.email_send_code(purpose="not-allowed", email="a@b.com")
        assert hasattr(resp, "status_code") and resp.status_code == 400

    def test_send_code_invalid_email_rsplit_valueerror(self) -> None:
        try:
            svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="invalid-email")
            assert False, "ValueError가 발생해야 함"
        except ValueError:
            pass

    @override_settings(**LOC_MEM_EMAIL)
    def test_send_code_rate_limit_returns_429(self) -> None:
        with (
            patch.object(svc, "DEFAULT_FROM_EMAIL", "no-reply@example.com", create=True),
            patch.object(svc, "RESEND_COOLDOWN_SECONDS", 60, create=True),
        ):
            ok = svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="u@ex.com")
            assert isinstance(ok, dict)
            again = svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="u@ex.com")
            assert hasattr(again, "status_code") and again.status_code == 429

    @override_settings(**LOC_MEM_EMAIL)
    def test_send_code_sendmail_failure_rolls_back(self) -> None:
        with (
            patch.object(svc, "DEFAULT_FROM_EMAIL", "no-reply@example.com", create=True),
            patch.object(svc, "RESEND_COOLDOWN_SECONDS", 60, create=True),
            patch.object(svc, "ONE_TIME_TTL_SECONDS", 600, create=True),
            patch("apps.users.services.email_verification_services.send_mail", side_effect=RuntimeError("SMTP FAIL")),
        ):
            try:
                svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="u@ex.com")
                assert False, "예외가 발생해야 함"
            except RuntimeError:
                pass
            assert cache.get(svc._rate_key("u@ex.com")) is None

    # --- 코드 확인 ---
    @override_settings(**LOC_MEM_EMAIL)
    def test_confirm_code_success_clears_purpose_keys(self) -> None:
        with (
            patch.object(svc, "DEFAULT_FROM_EMAIL", "no-reply@example.com", create=True),
            patch.object(svc, "ATTEMPT_LOCK_SECONDS", 60, create=True),
            patch.object(svc, "GLOBAL_LOCK_SECONDS", 60, create=True),
            patch.object(svc, "GLOBAL_MAX_FAILS", 5, create=True),
            patch.object(svc, "MAX_FAIL_ATTEMPTS", 3, create=True),
            patch.object(svc, "VERIFY_TOKEN_EXPIRES_SECONDS", 300, create=True),
            patch("apps.users.services.email_verification_services.issue_verify_token", return_value="VTOK-123"),
        ):
            meta = svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="x@ExAmPle.Com")
            assert isinstance(meta, dict)
            rid = meta["request_id"]
            code = _extract_code_from_outbox()

            to = "x@example.com"
            fk = svc._fail_key(to, EmailVerificationPurpose.SIGNUP)
            cache.set(fk, 1, timeout=60)

            resp = svc.email_confirm_code(
                purpose=EmailVerificationPurpose.SIGNUP,
                email="x@ExAmPle.Com",
                verification_code=code,
                request_id=rid,
            )
            assert isinstance(resp, dict)
            assert resp["verify_token"] == "VTOK-123"
            assert resp["expires_in"] == 300

            pk = svc._pending_key(to, EmailVerificationPurpose.SIGNUP, rid)
            assert cache.get(pk) is None
            assert cache.get(fk) is None

            lk = svc._lock_key(to, EmailVerificationPurpose.SIGNUP)
            assert cache.get(lk) is None

    def test_confirm_code_invalid_purpose_returns_400(self) -> None:
        resp = svc.email_confirm_code(purpose="unknown", email="a@b.com", verification_code="123456", request_id="abc")
        assert hasattr(resp, "status_code") and resp.status_code == 400

    @override_settings(**LOC_MEM_EMAIL)
    def test_confirm_code_global_lock_and_purpose_lock_short_circuit(self) -> None:
        with patch.object(svc, "DEFAULT_FROM_EMAIL", "no-reply@example.com", create=True):
            m = svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="lock@ex.com")
            assert isinstance(m, dict)
            rid = m["request_id"]

            gk = svc._global_lock_key("lock@ex.com")
            cache.set(gk, "1", timeout=60)
            resp1 = svc.email_confirm_code(
                purpose=EmailVerificationPurpose.SIGNUP,
                email="lock@ex.com",
                verification_code="000000",
                request_id=rid,
            )
            assert hasattr(resp1, "status_code") and resp1.status_code == 429

            cache.delete(gk)
            pk = svc._lock_key("lock@ex.com", EmailVerificationPurpose.SIGNUP)
            cache.set(pk, "1", timeout=60)
            resp2 = svc.email_confirm_code(
                purpose=EmailVerificationPurpose.SIGNUP,
                email="lock@ex.com",
                verification_code="000000",
                request_id=rid,
            )
            assert hasattr(resp2, "status_code") and resp2.status_code == 429

    @override_settings(**LOC_MEM_EMAIL)
    def test_confirm_code_pending_not_found_returns_404(self) -> None:
        with (
            patch.object(svc, "ATTEMPT_LOCK_SECONDS", 60, create=True),
            patch.object(svc, "GLOBAL_LOCK_SECONDS", 60, create=True),
        ):
            resp = svc.email_confirm_code(
                purpose=EmailVerificationPurpose.SIGNUP,
                email="z@ex.com",
                verification_code="123456",
                request_id="deadbeef",
            )
            assert hasattr(resp, "status_code") and resp.status_code == 404

    @override_settings(**LOC_MEM_EMAIL)
    def test_confirm_code_wrong_code_400_then_threshold_429_then_locked_429(self) -> None:
        with (
            patch.object(svc, "DEFAULT_FROM_EMAIL", "no-reply@example.com", create=True),
            patch.object(svc, "ATTEMPT_LOCK_SECONDS", 60, create=True),
            patch.object(svc, "GLOBAL_LOCK_SECONDS", 60, create=True),
            patch.object(svc, "GLOBAL_MAX_FAILS", 2, create=True),
            patch.object(svc, "MAX_FAIL_ATTEMPTS", 2, create=True),
        ):
            send_meta = svc.email_send_code(purpose=EmailVerificationPurpose.SIGNUP, email="y@Ex.com")
            assert isinstance(send_meta, dict)
            rid = send_meta["request_id"]

            r1 = svc.email_confirm_code(
                purpose=EmailVerificationPurpose.SIGNUP,
                email="y@Ex.com",
                verification_code="000000",
                request_id=rid,
            )
            assert hasattr(r1, "status_code") and r1.status_code == 400

            r2 = svc.email_confirm_code(
                purpose=EmailVerificationPurpose.SIGNUP,
                email="y@Ex.com",
                verification_code="111111",
                request_id=rid,
            )
            assert hasattr(r2, "status_code") and r2.status_code == 429

            r3 = svc.email_confirm_code(
                purpose=EmailVerificationPurpose.SIGNUP,
                email="y@Ex.com",
                verification_code="222222",
                request_id=rid,
            )
            assert hasattr(r3, "status_code") and r3.status_code == 429


# ============================================================================
# 3) 이메일 인증 퍼미션 테스트 (EmailVerifiedPermission)
#   - 글로벌 인증기를 비활성화해 401 간섭 제거
#   - verify_and_consume는 사용 위치(apps.users.permissions)에서 패치
# ============================================================================
class GoodEmailBoundView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [EmailVerifiedPermission]
    purpose = EmailVerificationPurpose.CHANGE_EMAIL

    def post(self, request: Request) -> Response:
        claims = getattr(request, "email_verify_claims", None)
        return Response({"ok": True, "claims": claims}, status=status.HTTP_200_OK)


class NoPurposeView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [EmailVerifiedPermission]

    def post(self, request: Request) -> Response:
        return Response({"should_not": "reach"}, status=status.HTTP_200_OK)


urlpatterns = [
    path("email-verify/good/", GoodEmailBoundView.as_view(), name="email-verify-good"),
    path("email-verify/nopurpose/", NoPurposeView.as_view(), name="email-verify-nopurpose"),
]


@override_settings(
    ROOT_URLCONF=__name__,
    REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": [], "DEFAULT_PERMISSION_CLASSES": []},
)
class TestEmailVerifiedPermission(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client: APIClient = APIClient()
        self.good_url = reverse("email-verify-good")
        self.nopurpose_url = reverse("email-verify-nopurpose")

    def _post_json(
        self, url: str, data: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None
    ) -> Response:
        """테스트 요청 헬퍼 (mypy가 **headers를 잘못 추론하는 문제 방지)"""
        extra: Dict[str, Any] = {} if headers is None else cast(Dict[str, Any], headers)
        return self.client.post(url, data=data, format="json", **extra)

    def test_denied_when_purpose_missing(self) -> None:
        resp = self._post_json(self.nopurpose_url, {"email": "u@example.com"})
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn("인증 목적이 지정되지 않았습니다.", resp.data.get("detail", ""))

    def test_denied_when_token_missing(self) -> None:
        payload: Dict[str, Any] = {"email": "u@example.com"}
        resp = self._post_json(self.good_url, payload)
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn("검증 토큰이 필요합니다.", resp.data.get("detail", ""))

    def test_denied_when_email_missing(self) -> None:
        headers = {"HTTP_X_EMAIL_VERIFY_TOKEN": "HDR-TOKEN"}
        resp = self._post_json(self.good_url, {}, headers=headers)
        self.assertEqual(resp.status_code, 403, resp.content)

    @patch("apps.users.permissions.verify_and_consume")
    def test_denied_when_verify_returns_error_response(self, mock_verify: Any) -> None:
        """verify_and_consume가 에러 Response를 돌리면 403"""
        mock_verify.side_effect = AuthenticationFailed({"error": "토큰이 유효하지 않습니다."})

        headers = {"HTTP_X_EMAIL_VERIFY_TOKEN": "HDR-TOKEN"}
        payload = {"email": "u@example.com", "verify_token": "BODY-TOKEN"}
        resp = self._post_json(self.good_url, payload, headers=headers)

        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn("토큰이 유효하지 않습니다.", resp.data.get("error", ""))

        called_args, called_kwargs = mock_verify.call_args
        self.assertEqual(called_args[0], "HDR-TOKEN")
        self.assertEqual(called_kwargs["expected_purpose"], EmailVerificationPurpose.CHANGE_EMAIL)

    @patch("apps.users.permissions.verify_and_consume")
    def test_allowed_when_verify_returns_claims_and_sets_on_request(self, mock_verify: Any) -> None:
        """검증 성공 시 200, request.email_verify_claims 설정"""
        claims: Dict[str, Any] = {"sub": "u@example.com", "purpose": "change_email", "jti": "abc123", "exp": 1234567890}
        mock_verify.return_value = claims

        headers = {"HTTP_X_EMAIL_VERIFY_TOKEN": "HDR-TOKEN"}
        payload = {"email": "u@example.com", "verify_token": "BODY-TOKEN"}
        resp = self._post_json(self.good_url, payload, headers=headers)

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data.get("ok") is True)
        self.assertEqual(resp.data.get("claims"), claims)

        called_args, called_kwargs = mock_verify.call_args
        self.assertEqual(called_args[0], "HDR-TOKEN")
        self.assertEqual(called_kwargs["expected_purpose"], EmailVerificationPurpose.CHANGE_EMAIL)
