# apps/chat/tests/test_chat_consumers.py
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.chat.consumers import ChatConsumer
from apps.chat.models.chat_message import ChatMessage
from apps.studies.models.groups import GroupMember, StudyGroup

User = get_user_model()


class ChatConsumerTest(APITestCase):
    """
    Test suite for the ChatConsumer.
    Uses WebsocketCommunicator to test consumer logic directly without a live server.
    """

    async def test_chat_message_broadcasts_to_all_users_in_group(self) -> None:
        """
        Tests that a message sent by one user is broadcast to all users in the study group.
        """
        # 1. Create test data: 2 users, 1 study group
        user1 = await sync_to_async(User.objects.create_user)(
            email="testuser1@example.com",
            password="password123",
            nickname="testuser1",
            phone_number="01011111111",
            name="Test User 1",
            gender="M",
            birthday="2000-01-01",
        )
        user2 = await sync_to_async(User.objects.create_user)(
            email="testuser2@example.com",
            password="password123",
            nickname="testuser2",
            phone_number="01022222222",
            name="Test User 2",
            gender="F",
            birthday="2000-01-02",
        )
        study_group = await sync_to_async(StudyGroup.objects.create)(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )
        await sync_to_async(GroupMember.objects.create)(study_group=study_group, user=user1, is_leader=True)
        await sync_to_async(GroupMember.objects.create)(study_group=study_group, user=user2)

        # 2. Set up WebSocket communicators for both users
        communicator1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.id}/chat/",
        )
        communicator1.scope["user"] = user1
        communicator1.scope["url_route"] = {"kwargs": {"study_group_id": study_group.id}}

        communicator2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/study-groups/{study_group.id}/chat/",
        )
        communicator2.scope["user"] = user2
        communicator2.scope["url_route"] = {"kwargs": {"study_group_id": study_group.id}}

        # 3. Connect both users to the WebSocket
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected2)

        # 4. User1 sends a test message
        test_message_content = "Hello, this is a test message from user1."
        await communicator1.send_json_to({"type": "chat.message", "content": test_message_content})

        # 5. Verify both users received the message
        response1 = await communicator1.receive_json_from()
        self.assertEqual(response1["type"], "chat.message")
        self.assertEqual(response1["message"], test_message_content)
        self.assertEqual(response1["sender_id"], user1.id)

        response2 = await communicator2.receive_json_from()
        self.assertEqual(response2["type"], "chat.message")
        self.assertEqual(response2["message"], test_message_content)
        self.assertEqual(response2["sender_id"], user1.id)

        # 6. Verify the message is saved in the database
        message_exists = await ChatMessage.objects.filter(
            study_group=study_group,
            sender=user1,
            content=test_message_content,
        ).aexists()
        self.assertTrue(message_exists)

        # 7. Disconnect both communicators
        await communicator1.disconnect()
        await communicator2.disconnect()
