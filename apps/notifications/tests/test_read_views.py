from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient, APITestCase

from apps.notifications.models import Notification

User = get_user_model()


class NotificationReadAPITestCase(APITestCase):
    def setUp(self) -> None:
        """테스트용 사용자와 알림 데이터 생성"""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            nickname="testuser",
            name="테스트유저",
            phone_number="01012345678",
            birthday="2000-12-31",
            gender="MALE",
        )

        # 로그인 처리
        self.client.force_authenticate(user=self.user)

        # 테스트용 알림 데이터 생성
        self.notification_unread = Notification.objects.create(
            user=self.user,
            content="읽지 않은 알림",
            is_read=False,
        )
        self.notification_read = Notification.objects.create(
            user=self.user,
            content="이미 읽은 알림",
            is_read=True,
        )

    def test_mark_notification_as_read_success(self) -> None:
        """읽지 않은 알림을 읽음 처리하면 is_read=True로 변경되어야 한다"""
        url = reverse("notifications:notification-read", kwargs={"notification_id": self.notification_unread.id})
        response: Response = self.client.post(url)
        self.notification_unread.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.notification_unread.is_read)
        self.assertEqual(response.data["detail"], "ok")

    def test_mark_notification_already_read(self) -> None:
        """이미 읽은 알림에 다시 PATCH 요청하면 200 OK지만 상태는 그대로"""
        url = reverse("notifications:notification-read", kwargs={"notification_id": self.notification_read.id})
        response: Response = self.client.post(url)
        self.notification_read.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.notification_read.is_read)
        self.assertEqual(response.data["detail"], "ok")

    def test_mark_notification_not_found(self) -> None:
        """존재하지 않는 알림 ID로 요청하면 404 반환"""
        url = reverse("notifications:notification-read", kwargs={"notification_id": 9999999})
        response: Response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "not found")

    def test_mark_all_notifications_as_read(self) -> None:
        """읽지 않은 모든 알림을 한 번에 읽음 처리"""
        url = reverse("notifications:notification-read-all")
        response: Response = self.client.post(url)

        unread_count = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("ok", response.data["detail"])
        self.assertEqual(unread_count, 0)
