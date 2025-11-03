from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import Reason
from apps.users.models import Withdrawal

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

User = get_user_model()


class UserWithdrawalAPIViewTests(IsolatedRedisTestClient):
    """
    회원 탈퇴 API 테스트
    """

    def setUp(self) -> None:
        self.url = reverse("users:user_withdrawal")
        self.user = User.objects.create_user(
            email="test@example.com",
            name="테스터",
            nickname="tester",
            phone_number="01012345678",
            gender="male",
            birthday="2000-01-01",
            is_active=True,
        )
        self.client.force_authenticate(self.user)

    def test_withdraw_success(self) -> None:
        """
        정상 탈퇴 요청
        """

        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        jti = refresh["jti"]

        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = refresh_str

        payload = {
            "reason": Reason.LACK_OF_INTEREST,
            "reason_detail": "이용이 어렵습니다.",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "계정이 비활성화되었습니다.")

        # 사용자 비활성화 여부 확인
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        # Withdrawal 레코드 생성 확인
        withdrawal = Withdrawal.objects.get(user=self.user)
        self.assertEqual(withdrawal.reason, Reason.LACK_OF_INTEREST)
        self.assertEqual(withdrawal.reason_detail, "이용이 어렵습니다.")
        self.assertEqual(withdrawal.due_date, timezone.now().date() + timedelta(days=14))

        # refresh 토큰이 블랙리스트에 들어갔는지 확인
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=jti).exists(),
            "탈퇴 시점에 refresh 토큰이 블랙리스트로 등록되어야 합니다.",
        )

        # 응답에서 쿠키가 삭제됐는지 확인
        deleted_cookie = response.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
        self.assertIsNotNone(
            deleted_cookie,
            "탈퇴 응답에서 refresh 쿠키를 삭제하는 Set-Cookie가 있어야 합니다.",
        )
        self.assertEqual(deleted_cookie.value, "")
        # max-age 가 문자열로 올 수도 있어서 둘 다 허용
        self.assertIn(str(deleted_cookie["max-age"]), ("0", "0.0"))


    def test_withdraw_duplicate_request(self) -> None:
        """
        이미 탈퇴 요청이 존재할 경우 오류 반환
        """
        Withdrawal.objects.create(
            user=self.user,
            reason=Reason.NO_LONGER_NEEDED,
            reason_detail="테스트용",
            due_date=date.today() + timedelta(days=14),
        )

        payload = {
            "reason": Reason.LACK_OF_INTEREST,
            "reason_detail": "이용이 어렵습니다.",
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 탈퇴 요청이 존재합니다.", str(response.data))

    def test_withdraw_inactive_user(self) -> None:
        """
        이미 비활성화된 사용자는 탈퇴 요청 불가
        """
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        payload = {
            "reason": Reason.LACK_OF_INTEREST,
            "reason_detail": "테스트",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 탈퇴 처리된 계정입니다.", str(response.data))


class UserAccountRecoveryTests(IsolatedRedisTestClient):
    """
    사용자 계정 복구 API 테스트
    """

    def setUp(self) -> None:
        self.url = reverse("users:user_recovery_account")
        self.user = User.objects.create_user(
            email="recover@example.com",
            name="복구테스터",
            nickname="recover",
            phone_number="01044445555",
            gender="female",
            birthday="1998-08-08",
            is_active=False,  # 탈퇴 상태 가정
        )
        self.withdrawal = Withdrawal.objects.create(
            user=self.user,
            reason=Reason.NO_LONGER_NEEDED,
            reason_detail="통합 테스트용",
            due_date=timezone.now().date() + timedelta(days=14),
        )

    @patch("apps.users.views.user_withdrawals_views.EmailVerifiedPermission.has_permission")
    def test_account_recovery_success(self, mock_has_permission: Any) -> None:
        """
        탈퇴 계정 복구 성공
        """

        # 권한을 통과시키면서, 뷰가 읽을 claims를 request에 주입
        def _allow_and_inject(request: Request, view: APIView) -> bool:
            setattr(request, "email_verify_claims", {"sub": self.user.email})
            return True

        # 대체 함수 지정
        mock_has_permission.side_effect = _allow_and_inject

        resp = self.client.post(self.url, {"verify_token": "dummy-token"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("detail"), "계정 복구가 완료되었습니다.")

        # DB 변경 확인: user 활성화 + withdrawal 삭제
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(Withdrawal.objects.filter(user=self.user).exists())

    @patch("apps.users.views.user_withdrawals_views.EmailVerifiedPermission.has_permission")
    def test_account_recovery_user_not_found(self, mock_has_permission: Any) -> None:
        """
        유효하지 않은 토큰(sub 이메일)로 복구 시도
        """

        def _allow_and_inject(request: Request, view: APIView) -> bool:
            setattr(request, "email_verify_claims", {"sub": "notfound@example.com"})
            return True

        mock_has_permission.side_effect = _allow_and_inject

        resp = self.client.post(self.url, {"verify_token": "dummy-token"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("해당 이메일의 사용자를 찾을 수 없습니다.", str(resp.data))
