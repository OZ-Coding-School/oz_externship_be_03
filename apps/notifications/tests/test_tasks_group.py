import asyncio
from datetime import datetime, timezone

from django.contrib.auth import get_user_model

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import notification_pubsub
from apps.notifications.tasks import send_study_group_notification
from apps.studies.models.groups import StudyGroup
from apps.users.enums import Gender

User = get_user_model()


class TasksTest(IsolatedRedisTestClient):
    def setUp(self) -> None:
        super().setUp()

        from datetime import date

        self.user = User.objects.create_user(
            email="test@test.com",
            password="pass123",
            nickname="test",
            name="테스트",
            phone_number="010-1456-7890",
            birthday=date(1995, 1, 11),
            gender=Gender.MALE,
        )

        self.notification = Notification.objects.create(
            user=self.user,
            content="테스트 알림입니다.",
            type=Notification.NotificationType.APPLICATION_CREATED,
            back_url_link="https://example.com/test",
        )

        self.study_group = StudyGroup.objects.create(
            name="오즈코딩스쿨",
            introduction="장고 익스턴십",
            max_headcount=5,
            start_at=datetime.now(timezone.utc),
            end_at=datetime.now(timezone.utc),
        )

    async def test_send_to_pubsub_group(self) -> None:
        """to redis 그룹 알림 전송 테스트"""
        messages = []

        async def group_message_listener() -> None:
            async for message in notification_pubsub.subscribe_notification(group_ids=[str(self.study_group.id)]):
                messages.append(message)
                if len(messages) >= 1:
                    break

        listener_task = asyncio.create_task(group_message_listener())

        await asyncio.sleep(1.0)

        # 그룹 알림 전송
        await send_study_group_notification(self.notification.id, str(self.study_group.id))

        try:
            await asyncio.wait_for(listener_task, timeout=5.0)
        except asyncio.TimeoutError:
            listener_task.cancel()

        self.assertEqual(len(messages), 1)
        data = messages[0]
        self.assertEqual(data["id"], self.notification.id)
        self.assertEqual(data["content"], self.notification.content)
