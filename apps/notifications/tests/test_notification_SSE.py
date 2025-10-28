import asyncio
import json
import logging
import time
from datetime import date, timezone, datetime

from django.contrib.auth import get_user_model

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import RedisPubSubService

from apps.users.enums import Gender

User = get_user_model()

logger = logging.getLogger(__name__)

class TestRedisPubSubService(IsolatedRedisTestClient):

    def setUp(self) -> None:
        super().setUp() #부모 클래스 세팅

        self.pubsub_service = RedisPubSubService()

        self.author = User.objects.create(
            email="test@test.com",
            password="pass123",
            nickname="test",
            name="test",
            phone_number="010-1111-2222",
            birthday=date(1995,1,11),
            gender=Gender.MALE,
        )
        self.applicant = User.objects.create(
            email="test1@test.com",
            password="pass123",
            nickname="test1",
            name="지원자",
            phone_number="010-1111-2223",
            birthday=date(1995,1,12),
            gender=Gender.MALE,
        )

    async def test_redis_connection(self):
        ping_result = await self.pubsub_service.redis_client.ping()
        self.assertTrue(ping_result)
        print("연결완료")

        user_id = self.author.id
        channel = self.pubsub_service.get_user_channel(user_id)
        expected = f"notifications:user_{user_id}"
        self.assertEqual(channel, expected)


    async def test_redis_publish(self):
        user_id = self.author.id

        test_notification = {
            "id": 1,
            "type": Notification.NotificationType.APPLICATION_CREATED,
            "content" : "테스트입니다.",
            "created_at" : datetime.now(timezone.utc).isoformat(),
            "is_read" : False,
        }
        print(f"발행할 알림 데이터:{test_notification}")

        pubsub = self.pubsub_service.redis_client.pubsub()
        channel = self.pubsub_service.get_user_channel(user_id)
        print(f"channel:{channel}")
        await pubsub.subscribe(channel)
        print("채널 구독 완료")

        await asyncio.sleep(0.1)

        await self.pubsub_service.publish_notification(user_id, test_notification)
        print("알림 발행 완료")
        message = await pubsub.get_message(timeout=1)
        print(f"message:{message}")
        if message and message['type']=='subscribe':
            message = await pubsub.get_message(timeout=2)
            print(f"second message:{message}")

        if message and message['type'] == 'message':
            received_data = json.loads(message['data'])

            self.assertEqual(received_data['id'],1)
            self.assertEqual(received_data['content'],"테스트입니다.")
            self.assertEqual(received_data['type'],Notification.NotificationType.APPLICATION_CREATED)

        else:
            self.fail("메시지를 받지 못했습니다.")

        await pubsub.close()

