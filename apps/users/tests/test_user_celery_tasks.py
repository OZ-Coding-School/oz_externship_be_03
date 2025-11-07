from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, Withdrawal
from apps.users.tasks import UNLINK_TIMEOUT, delete_withdrawn_users

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()


@override_settings(
    # Celery: 비동기 호출을 테스트에서 동기 실행
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    # 외부 설정 값 주입
    KAKAO_UNLINK_URL=settings.KAKAO_UNLINK_URL,
    KAKAO_ADMIN_KEY="dummy-admin-key",
)
class DeleteWithdrawnUsersTests(IsolatedRedisTestClient):

    def setUp(self) -> None:
        self.today = timezone.localdate()

    def _make_user_minimal(self, *, email: str, is_active: bool = False) -> UserModel:
        """
        User 모델의 NOT NULL 필드를 모두 채우는 최소 유저 생성 헬퍼.
        """
        suffix = uuid4().hex[:6]
        user = User.objects.create_user(
            email=email,
            password="testpwd",
            is_active=is_active,
            name=f"테스트",
            nickname=f"nick{suffix}",
            phone_number=f"01012{suffix}",
            birthday=date(1990, 1, 1),
            gender=Gender.MALE,
        )
        return user

    def _make_withdrawn_user(self, *, user: UserModel, due_offset_days: int) -> Withdrawal:
        withdrawn_user = Withdrawal.objects.create(user=user, due_date=self.today + timedelta(days=due_offset_days))
        return withdrawn_user

    def _assert_withdrawal_user_null(self, withdrawn_user: Withdrawal) -> None:
        withdrawn_user.refresh_from_db()
        # User 삭제 후 Withdrawal.user_id가 NULL로 남는지 확인
        assert withdrawn_user.user_id is None

    @patch("apps.users.tasks.requests.post")
    def test_end_to_end_basic(self, mock_post: Any) -> None:
        """
        - due_date 지난 유저 2명(user1,user2) → 삭제 대상
        - 아직 due_date 지나지 않은 1명(user3) → 남아있음
        - Kakao 연동된 유저만 unlink 호출
        """
        # user1: due_date 지남, KAKAO 연동
        user1 = self._make_user_minimal(email="user1@example.com", is_active=False)
        withdrawn_user1 = self._make_withdrawn_user(user=user1, due_offset_days=-1)
        SocialUser.objects.create(user=user1, provider=Provider.KAKAO, provider_id="k-111")

        # user2: due_date 오늘, NAVER 연동(=unlink 대상 아님)
        user2 = self._make_user_minimal(email="user2@example.com", is_active=False)
        withdrawn_user2 = self._make_withdrawn_user(user=user2, due_offset_days=0)
        SocialUser.objects.create(user=user2, provider=Provider.NAVER, provider_id="g-222")

        # user3: due_date 미래, KAKAO 연동
        user3 = self._make_user_minimal(email="user3@example.com", is_active=False)
        withdrawn_user3 = self._make_withdrawn_user(user=user3, due_offset_days=+1)
        SocialUser.objects.create(user=user3, provider=Provider.KAKAO, provider_id="k-333")

        # 외부 API 정상 모킹
        mock_resp = type(
            "Resp",
            (),
            {
                "status_code": 200,
                "headers": {"Content-Type": "application/json"},
                "json": lambda self: {"id": "k-111"},
            },
        )()
        mock_post.return_value = mock_resp

        # 실행(엔드투엔드) - 배치 10
        processed = delete_withdrawn_users.delay(batch_size=10).get()
        self.assertEqual(processed, 2)

        # DB 검증: user1,user2 삭제 / user3 생존
        self.assertFalse(User.objects.filter(id=user1.id).exists())
        self.assertFalse(User.objects.filter(id=user2.id).exists())
        self.assertTrue(User.objects.filter(id=user3.id).exists())

        # Withdrawal FK(on_delete=SET_NULL) 검증
        self._assert_withdrawal_user_null(withdrawn_user1)
        self._assert_withdrawal_user_null(withdrawn_user2)

        # unlink는 user1만 1회 호출
        mock_post.assert_called_once_with(
            settings.KAKAO_UNLINK_URL,
            headers={"Authorization": "KakaoAK dummy-admin-key"},
            data={"target_id_type": "user_id", "target_id": "k-111"},
            timeout=UNLINK_TIMEOUT,
        )

    def test_early_exit_when_no_targets(self) -> None:
        """
        - due_date가 지났거나 오늘인 건이 전혀 없으면 0 반환 후 즉시 종료
        - 외부 호출도 없어야 함
        """
        user = self._make_user_minimal(email="user@example.com", is_active=False)
        withdrawn_user = self._make_withdrawn_user(user=user, due_offset_days=+3)

        with patch("apps.users.tasks.requests.post") as mock_post:
            processed = delete_withdrawn_users.delay(batch_size=50).get()

        self.assertEqual(processed, 0)
        self.assertTrue(User.objects.filter(id=user.id).exists())
        mock_post.assert_not_called()
