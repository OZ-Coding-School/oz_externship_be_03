import asyncio
import json
import logging
from datetime import date, datetime, timezone

from django.contrib.auth import get_user_model
from redis.asyncio import Redis

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import RedisPubSubService
from apps.users.enums import Gender

User = get_user_model()

logger = logging.getLogger(__name__)


class TestRedisPubSubService(IsolatedRedisTestClient):

    def setUp(self) -> None:
        super().setUp()  # 부모 클래스 세팅
        logging.disable(logging.CRITICAL)
        self.pubsub_service = RedisPubSubService()

        self.author = User.objects.create(
            email="test@test.com",
            password="pass123",
            nickname="test",
            name="test",
            phone_number="010-1111-2222",
            birthday=date(1995, 1, 11),
            gender=Gender.MALE,
        )

        self.test_notification = {
            "id": 1,
            "type": Notification.NotificationType.APPLICATION_CREATED,
            "content": "테스트입니다.",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_read": False,
        }

    async def test_redis_connection_channel_individual(self) -> None:
        """redis 연결 테스트"""
        ping_result = await self.pubsub_service.redis_client.ping()
        self.assertTrue(ping_result)

        user_id = self.author.id
        channel = self.pubsub_service.get_user_channel(user_id)
        expected = f"notifications:user_{user_id}"
        self.assertEqual(channel, expected)

    async def test_redis_connection_channel_group(self) -> None:
        group_id = "study_group_1"
        channel = self.pubsub_service.get_group_channel(group_id)
        expected = f"notifications:group_{group_id}"
        self.assertEqual(channel, expected)

    async def test_redis_publish_individual(self) -> None:
        """알림 발행 테스트"""
        user_id = self.author.id

        pubsub = self.pubsub_service.redis_client.pubsub()
        channel = self.pubsub_service.get_user_channel(user_id)

        await pubsub.subscribe(channel)

        await asyncio.sleep(0.1)

        await self.pubsub_service.publish_notification(user_id, self.test_notification)

        message = await pubsub.get_message(timeout=1)

        if message and message["type"] == "subscribe":
            message = await pubsub.get_message(timeout=2)

        if message and message["type"] == "message":
            received_data = json.loads(message["data"])

            self.assertEqual(received_data["id"], 1)
            self.assertEqual(received_data["content"], "테스트입니다.")
            self.assertEqual(received_data["type"], Notification.NotificationType.APPLICATION_CREATED)

        else:
            self.fail("메시지를 받지 못했습니다.")

        await pubsub.close()

    async def test_redis_pub_error_case(self) -> None:
        """알림 발행 에러 테스트"""
        redis_client = self.pubsub_service.redis_client

        try:
            fake_client = Redis(host="invalid-host", port=1111, socket_connect_timeout=1)
            self.pubsub_service.redis_client = fake_client
            user_id = self.author.id

            try:
                await self.pubsub_service.publish_notification(user_id, self.test_notification)
            except Exception as e:
                print(f"에러 발생:{type(e).__name__}:{e}")
                self.assertIn(type(e).__name__, ["ConnectionError"])

        finally:
            self.pubsub_service.redis_client = redis_client

    async def test_publish_group_notification_error_handling(self) -> None:
        """그룹 알림 발행 에러 핸들링 테스트"""
        redis_client = self.pubsub_service.redis_client

        try:
            fake_client = Redis(host="invalid-host", port=1111, socket_connect_timeout=1)
            self.pubsub_service.redis_client = fake_client

            await self.pubsub_service.publish_group_notification("test_group", self.test_notification)

        finally:
            self.pubsub_service.redis_client = redis_client

    async def test_redis_subscribe_individual(self) -> None:
        """알림 구독 테스트"""
        user_id = self.author.id

        async def publish_after_delay() -> None:
            await asyncio.sleep(0.2)
            await self.pubsub_service.publish_notification(user_id, self.test_notification)

        publish_task = asyncio.create_task(publish_after_delay())

        received_count = 0
        async for notification in self.pubsub_service.subscribe_notification(user_id=user_id):
            self.assertEqual(notification["content"], "테스트입니다.")
            received_count += 1
            if received_count >= 1:
                break

        await publish_task
        self.assertEqual(received_count, 1)

    async def test_redis_subscribe_error_case(self) -> None:
        """알림 구독 에러 테스트"""
        redis_client = self.pubsub_service.redis_client

        try:
            fake_client = Redis(host="invalid-host", port=1111, socket_connect_timeout=1)
            self.pubsub_service.redis_client = fake_client

            user_id = self.author.id

            received_count = 0
            async for notification in self.pubsub_service.subscribe_notification(user_id=user_id):
                received_count += 1
                if received_count >= 1:
                    break

            self.assertEqual(received_count, 0)

        finally:
            self.pubsub_service.redis_client = redis_client

    async def test_redis_publish_group(self) -> None:
        """그룹 알림 발행 테스트"""
        group_id = "test_group_1"

        pubsub = self.pubsub_service.redis_client.pubsub()
        channel = self.pubsub_service.get_group_channel(group_id)

        await pubsub.subscribe(channel)
        await asyncio.sleep(0.1)

        await self.pubsub_service.publish_group_notification(group_id, self.test_notification)

        message = await pubsub.get_message(timeout=1)

        if message and message["type"] =="subscribe":
            message = await pubsub.get_message(timeout=2)

        if message and message["type"] == "message":
            received_data = json.loads(message["data"])
            self.assertEqual(received_data["id"], 1)
            self.assertEqual(received_data["content"],"테스트입니다.")
        else:
            self.fail("그룹 메시지를 받지 못했습니다.")

        await pubsub.close()

    async def test_redis_subscribe_group(self) -> None:

        group_ids=["group_1","group_2"]

        async def publish_after_delay()-> None:
            await asyncio.sleep(0.2)
            await self.pubsub_service.publish_group_notification("group_1",self.test_notification)

        publish_task = asyncio.create_task(publish_after_delay())

        received_count = 0
        async for notification in self.pubsub_service.subscribe_notification(group_ids=group_ids):
            self.assertEqual(notification["content"], "테스트입니다.")
            received_count += 1
            if received_count >= 1:
                break

        await publish_task
        self.assertEqual(received_count, 1)


