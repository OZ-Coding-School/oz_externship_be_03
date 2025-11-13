from typing import Any, Set

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TransactionTestCase
from django_redis import get_redis_connection  # type: ignore[import-untyped]

from apps.chat.consumers import ChatConsumer
from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models.user import User


class ChatConsumerTest(TransactionTestCase):

    def setUp(self) -> None:
        cache.clear()

    def tearDown(self) -> None:
        cache.clear()

    @sync_to_async
    def _create_user(self, **kwargs: Any) -> User:
        """동기 방식으로 유저 생성 후 async로 래핑"""
        return User.objects.create_user(**kwargs)

    @sync_to_async
    def _create_study_group(self, **kwargs: Any) -> StudyGroup:
        """동기 방식으로 스터디 그룹 생성"""
        return StudyGroup.objects.create(**kwargs)

    @sync_to_async
    def _create_group_member(self, **kwargs: Any) -> GroupMember:
        """동기 방식으로 그룹 멤버 생성"""
        return GroupMember.objects.create(**kwargs)

    async def _create_chat_message(self, **kwargs: Any) -> ChatMessage:
        """비동기 방식으로 채팅 메시지 생성"""
        return await ChatMessage.objects.acreate(**kwargs)

    @sync_to_async
    def _get_redis_online_count(self, study_group_uuid: str) -> int:
        redis_key = f"online_users:{study_group_uuid}"
        redis_client = get_redis_connection("default")
        return int(redis_client.scard(redis_key))

    @sync_to_async
    def _get_redis_online_users(self, study_group_uuid: str) -> Set[str]:
        redis_key = f"online_users:{study_group_uuid}"
        redis_client = get_redis_connection("default")
        members = redis_client.smembers(redis_key)
        return {member.decode("utf-8") if isinstance(member, bytes) else member for member in members}

    async def test_connection_success(self) -> None:
        user = await self._create_user(
            email="testuser@example.com",
            password="password123",
            nickname="testuser",
            phone_number="01012345678",
            name="Test User",
            gender="M",
            birthday="2000-01-01",
        )
        study_group = await self._create_study_group(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )
        await self._create_group_member(study_group=study_group, user=user, is_leader=True)

        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator.scope["user"] = user
        communicator.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        self.assertIsNone(subprotocol)

        await communicator.disconnect()

    async def test_chat_message_broadcasts_to_all_users_in_group(self) -> None:
        """
        Tests that a message sent by one user is broadcast to all users in the study group.
        """
        # 1. Create test data: 2 users, 1 study group
        user1 = await self._create_user(
            email="testuser1@example.com",
            password="password123",
            nickname="testuser1",
            phone_number="01011111111",
            name="Test User 1",
            gender="M",
            birthday="2000-01-01",
        )
        user2 = await self._create_user(
            email="testuser2@example.com",
            password="password123",
            nickname="testuser2",
            phone_number="01022222222",
            name="Test User 2",
            gender="F",
            birthday="2000-01-02",
        )
        study_group = await self._create_study_group(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )
        await GroupMember.objects.acreate(study_group=study_group, user=user1, is_leader=True)
        await GroupMember.objects.acreate(study_group=study_group, user=user2)

        # 2. Set up WebSocket communicators for both users
        communicator1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator1.scope["user"] = user1
        communicator1.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        communicator2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator2.scope["user"] = user2
        communicator2.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        # 3. Connect both users to the WebSocket
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected2)

        try:
            await communicator1.receive_json_from(timeout=5)  # user1 connects, user1 receives its own join
            await communicator2.receive_json_from(timeout=5)  # user2 connects, user2 receives its own join
            await communicator1.receive_json_from(timeout=5)  # user2 connects, user1 receives user2's join

            # 4. User1 sends a test message
            test_message_content = "Hello, this is a test message from user1."
            await communicator1.send_json_to({"type": "chat.message", "content": test_message_content})

            # 5. Verify both users received the message
            response1 = await communicator1.receive_json_from(timeout=5)
            self.assertEqual(response1["type"], "chat.message")
            self.assertEqual(response1["content"], test_message_content)
            self.assertEqual(response1["sender"]["id"], str(user1.id))
            self.assertEqual(response1["sender"]["nickname"], user1.nickname)

            response2 = await communicator2.receive_json_from(timeout=5)
            self.assertEqual(response2["type"], "chat.message")
            self.assertEqual(response2["content"], test_message_content)
            self.assertEqual(response2["sender"]["id"], str(user1.id))
            self.assertEqual(response2["sender"]["nickname"], user1.nickname)

            # 6. Verify the message is saved in the database
            message_exists = await ChatMessage.objects.filter(
                study_group=study_group,
                sender=user1,
                content=test_message_content,
            ).aexists()
            self.assertTrue(message_exists)

        finally:
            # 7. Disconnect both communicators
            await communicator1.disconnect()
            await communicator2.disconnect()

    async def test_connection_failure_unauthenticated_user(self) -> None:
        study_group = await StudyGroup.objects.acreate(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )

        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        # User is not set, so it will be an AnonymousUser
        communicator.scope["user"] = AnonymousUser()
        communicator.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(subprotocol, 403)

        await communicator.disconnect()

    async def test_connection_failure_invalid_study_group(self) -> None:
        user = await self._create_user(
            email="testuser@example.com",
            password="password123",
            nickname="testuser",
            phone_number="01012345678",
            name="Test User",
            gender="M",
            birthday="2000-01-01",
        )
        # Use a non-existent study_group_uuid
        invalid_study_group_uuid = "00000000-0000-0000-0000-000000000000"

        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{invalid_study_group_uuid}/chat/",
        )
        communicator.scope["url_route"] = {"kwargs": {"study_group_uuid": invalid_study_group_uuid}}
        communicator.scope["user"] = user
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(subprotocol, 403)

        await communicator.disconnect()

        await communicator.disconnect()

    async def test_mark_messages_as_read_logic(self) -> None:
        user = await self._create_user(
            email="testuser@example.com",
            password="password123",
            nickname="testuser",
            phone_number="01012345678",
            name="Test User",
            gender="M",
            birthday="2000-01-01",
        )
        study_group = await self._create_study_group(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )
        await self._create_group_member(study_group=study_group, user=user)

        # 2. Create some messages
        await self._create_chat_message(study_group=study_group, sender=user, content="Message 1")
        last_message = await self._create_chat_message(study_group=study_group, sender=user, content="Message 2")

        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator.scope["user"] = user
        communicator.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        try:
            await communicator.receive_json_from(timeout=5)

            last_read_entry = await LastReadMessage.objects.select_related("message").aget(
                user=user, study_group=study_group
            )
            self.assertEqual(last_read_entry.message, last_message)
        finally:
            await communicator.disconnect()

    async def test_online_user_count_on_connect(self) -> None:
        user1 = await self._create_user(
            email="testuser1@example.com",
            password="password123",
            nickname="testuser1",
            phone_number="01011111111",
            name="Test User 1",
            gender="M",
            birthday="2000-01-01",
        )
        user2 = await self._create_user(
            email="testuser2@example.com",
            password="password123",
            nickname="testuser2",
            phone_number="01022222222",
            name="Test User 2",
            gender="F",
            birthday="2000-01-02",
        )
        study_group = await self._create_study_group(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )
        await self._create_group_member(study_group=study_group, user=user1, is_leader=True)
        await self._create_group_member(study_group=study_group, user=user2)

        count = await self._get_redis_online_count(str(study_group.uuid))
        self.assertEqual(count, 0)

        communicator1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator1.scope["user"] = user1
        communicator1.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)

        response1 = await communicator1.receive_json_from(timeout=5)
        self.assertEqual(response1["type"], "online.users")
        self.assertEqual(response1["count"], 1)
        self.assertEqual(len(response1["users"]), 1)
        self.assertEqual(response1["users"][0]["id"], str(user1.id))
        self.assertEqual(response1["users"][0]["nickname"], "testuser1")

        count = await self._get_redis_online_count(str(study_group.uuid))
        self.assertEqual(count, 1)

        communicator2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator2.scope["user"] = user2
        communicator2.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        connected2, _ = await communicator2.connect()
        self.assertTrue(connected2)

        response1_update = await communicator1.receive_json_from(timeout=5)
        self.assertEqual(response1_update["type"], "online.users")
        self.assertEqual(response1_update["count"], 2)
        self.assertEqual(len(response1_update["users"]), 2)

        response2 = await communicator2.receive_json_from(timeout=5)
        self.assertEqual(response2["type"], "online.users")
        self.assertEqual(response2["count"], 2)
        self.assertEqual(len(response2["users"]), 2)

        count = await self._get_redis_online_count(str(study_group.uuid))
        self.assertEqual(count, 2)

        online_users = await self._get_redis_online_users(str(study_group.uuid))
        self.assertIn(str(user1.id), online_users)
        self.assertIn(str(user2.id), online_users)

        await communicator1.disconnect()
        await communicator2.disconnect()

    async def test_online_user_count_on_disconnect(self) -> None:
        user1 = await self._create_user(
            email="testuser1@example.com",
            password="password123",
            nickname="testuser1",
            phone_number="01011111111",
            name="Test User 1",
            gender="M",
            birthday="2000-01-01",
        )
        user2 = await self._create_user(
            email="testuser2@example.com",
            password="password123",
            nickname="testuser2",
            phone_number="01022222222",
            name="Test User 2",
            gender="F",
            birthday="2000-01-02",
        )
        study_group = await self._create_study_group(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )
        await self._create_group_member(study_group=study_group, user=user1, is_leader=True)
        await self._create_group_member(study_group=study_group, user=user2)

        communicator1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator1.scope["user"] = user1
        communicator1.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        communicator2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.uuid}/chat/",
        )
        communicator2.scope["user"] = user2
        communicator2.scope["url_route"] = {"kwargs": {"study_group_uuid": str(study_group.uuid)}}

        await communicator1.connect()
        await communicator2.connect()

        await communicator1.receive_json_from(timeout=5)  # user1 connects, user1 receives its own join
        await communicator2.receive_json_from(timeout=5)  # user2 connects, user2 receives its own join
        await communicator1.receive_json_from(timeout=5)  # user2 connects, user1 receives user2's join

        count = await self._get_redis_online_count(str(study_group.uuid))
        self.assertEqual(count, 2)

        await communicator1.disconnect()

        response_leave = await communicator2.receive_json_from(timeout=5)
        self.assertEqual(response_leave["type"], "online.users")
        self.assertEqual(response_leave["count"], 1)
        self.assertEqual(len(response_leave["users"]), 1)
        self.assertEqual(response_leave["users"][0]["id"], str(user2.id))

        count = await self._get_redis_online_count(str(study_group.uuid))
        self.assertEqual(count, 1)

        online_users = await self._get_redis_online_users(str(study_group.uuid))
        self.assertNotIn(str(user1.id), online_users)
        self.assertIn(str(user2.id), online_users)

        await communicator2.disconnect()

        count = await self._get_redis_online_count(str(study_group.uuid))
        self.assertEqual(count, 0)
