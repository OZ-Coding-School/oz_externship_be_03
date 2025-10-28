import asyncio
import logging
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import notification_pubsub
from apps.notifications.views.SSE_views import notification_stream
from apps.users.enums import Gender

User = get_user_model()

logger = logging.getLogger(__name__)


class TestSSEViews(IsolatedRedisTestClient):

    def setUp(self) -> None:
        super().setUp()

        logging.disable(logging.CRITICAL)

        self.user = User.objects.create(
            email="test@test.com",
            password="pass123",
            nickname="test",
            name="test",
            phone_number="010-2222-1111",
            birthday=date(2020, 1, 1),
            gender=Gender.MALE,
        )

        self.other_user = User.objects.create(
            email="test2@test.com",
            password="pass123",
            nickname="test2",
            name="test2",
            phone_number="010-2222-1112",
            birthday=date(1995, 1, 11),
            gender=Gender.MALE,
        )

        self.test_notification = {
            "id": 1,
            "type": Notification.NotificationType.APPLICATION_CREATED,
            "content": "테스트입니다.",
            "created_at": datetime.now(),
            "back_url_link": "test/",
        }

    async def test_notification_stream(self) -> None:
        """SSE 스트림 테스트"""
        request = HttpRequest()
        request.user = self.user

        response = await notification_stream(request, self.user.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["Connection"], "keep-alive")

        async def publish_notification() -> None:
            await asyncio.sleep(0.2)
            await notification_pubsub.publish_notification(self.user.id, self.test_notification)

        publish_task = asyncio.create_task(publish_notification())

        stream_content = []
        if hasattr(response.streaming_content, "__aiter__"):
            async for chunk in response.streaming_content:
                stream_content.append(chunk.decode("utf-8"))
                if len(stream_content) >= 2:
                    break

        await publish_task

        self.assertIn('data:{"type": "connected"}', stream_content[0])
        self.assertIn('"content": "테스트입니다."', stream_content[1])
        self.assertIn('"type": "APPLICATIONS_CREATED"', stream_content[1])

    async def test_notification_stream_unauthenticated_user(self) -> None:
        """미인증 유저 테스트"""
        request = HttpRequest()
        request.user = type("User", (), {"is_authenticated": False})()

        response = await notification_stream(request, self.user.id)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "text/event-stream")

    async def test_notificaiton_stream_wrong_user(self) -> None:
        request = HttpRequest()
        request.user = self.other_user

        response = await notification_stream(request, self.user.id)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "text/event-stream")
