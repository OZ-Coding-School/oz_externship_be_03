from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import Notification
from apps.users.models import User


class NotificationListAPITestCase(APITestCase):
    """
    NotificationListAPIView 테스트
    """

    def setUp(self) -> None:
        # create_user 대신 직접 생성
        self.user = User.objects.create(
            email="test@example.com",
            nickname="tester",
            name="테스터",
            phone_number="01012345678",
            birthday="2000-01-01",
            gender="MALE",
        )
        self.user.set_password("password123")
        self.user.save()

        # 다른 사용자 (권한 테스트용)
        self.other_user = User.objects.create(
            email="other@example.com",
            nickname="other",
            name="다른유저",
            phone_number="01022223333",
            birthday="1999-12-31",
            gender="FEMALE",
        )
        self.other_user.set_password("password123")
        self.other_user.save()

        # 로그인 후 토큰 인증
        self.client.force_authenticate(user=self.user)

        # 테스트용 알림 생성
        Notification.objects.create(
            user=self.user,
            content="내 알림 1",
            type="SYSTEM",
        )
        Notification.objects.create(
            user=self.other_user,
            content="다른 사람 알림",
            type="CUSTOM",
        )

    def test_authenticated_user_can_view_own_notifications(self) -> None:
        """
        인증된 사용자는 자신의 알림만 조회 가능
        """
        url = reverse("notifications:notification-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["counts"]["total"], 1)
        self.assertEqual(response.data["results"][0]["content"], "내 알림 1")

    def test_unauthenticated_user_cannot_access_notification_list(self) -> None:
        """
        인증되지 않은 사용자는 접근 불가 (401)
        """
        self.client.force_authenticate(user=None)
        url = reverse("notifications:notification-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
