# apps/chat/tests/test_chat_consumers.py
import asyncio

from channels.testing import (  # type: ignore[import-untyped]
    AsgiTestCase,
    WebsocketCommunicator,
)
from django.contrib.auth import get_user_model

from apps.chat.consumers import ChatConsumer
from apps.chat.models.chat_message import ChatMessage
from apps.studies.models.groups import GroupMember, StudyGroup

User = get_user_model()


class ChatConsumerTest(AsgiTestCase):  # type: ignore[misc]
    def test_chat_message_broadcasts_to_all_users_in_group(self) -> None:
        """
        Tests that a message sent by one user is broadcast to all users in the study group.
        """

        async def _async_test_logic() -> None:
            # 1. Create test data: 2 users, 1 study group
            user1 = await User.objects.acreate_user(  # type: ignore[attr-defined]
                email="testuser1@example.com",
                password="password123",
                nickname="testuser1",
                phone_number="01011111111",
                name="Test User 1",
                gender="M",
                birthday="2000-01-01",
            )
            user2 = await User.objects.acreate_user(  # type: ignore[attr-defined]
                email="testuser2@example.com",
                password="password123",
                nickname="testuser2",
                phone_number="01022222222",
                name="Test User 2",
                gender="F",
                birthday="2000-01-02",
            )
            study_group = await StudyGroup.objects.acreate(
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
                f"/ws/study-groups/{study_group.id}/chat/",
            )
            communicator1.scope["user"] = user1

            communicator2 = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f"/ws/study-groups/{study_group.id}/chat/",
            )
            communicator2.scope["user"] = user2

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

        asyncio.run(_async_test_logic())

    def test_edit_message_success(self) -> None:
        """
        Tests that a message can be successfully edited by the sender.
        """

        async def _async_test_logic() -> None:
            user1 = await User.objects.acreate_user(
                email="testuser1@example.com",
                password="password123",
                nickname="testuser1",
                phone_number="01011111111",
                name="Test User 1",
                gender="M",
                birthday="2000-01-01",
            )
            study_group = await StudyGroup.objects.acreate(
                name="Test Study Group",
                max_headcount=10,
                start_at="2025-10-21T10:00:00Z",
                end_at="2025-11-21T10:00:00Z",
            )
            await GroupMember.objects.acreate(study_group=study_group, user=user1, is_leader=True)

            communicator1 = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f"/ws/study-groups/{study_group.id}/chat/",
            )
            communicator1.scope["user"] = user1
            connected, _ = await communicator1.connect()
            self.assertTrue(connected)

            # Send initial message
            initial_content = "Initial message."
            await communicator1.send_json_to({"type": "chat.message", "content": initial_content})
            response = await communicator1.receive_json_from()
            message_id = response["message_id"]

            # Edit message
            new_content = "Edited message."
            await communicator1.send_json_to({"type": "chat.edit_message", "message_id": message_id, "new_content": new_content})
            edited_response = await communicator1.receive_json_from()

            self.assertEqual(edited_response["type"], "chat.message.edited")
            self.assertEqual(edited_response["message_id"], message_id)
            self.assertEqual(edited_response["new_content"], new_content)
            self.assertEqual(edited_response["editor_id"], user1.id)

            # Verify message in DB
            updated_message = await ChatMessage.objects.aget(id=message_id)
            self.assertEqual(updated_message.content, new_content)

            await communicator1.disconnect()

        asyncio.run(_async_test_logic())

    def test_edit_message_not_sender(self) -> None:
        """
        Tests that a message cannot be edited by a non-sender.
        """

        async def _async_test_logic() -> None:
            user1 = await User.objects.acreate_user(
                email="testuser1@example.com",
                password="password123",
                nickname="testuser1",
                phone_number="01011111111",
                name="Test User 1",
                gender="M",
                birthday="2000-01-01",
            )
            user2 = await User.objects.acreate_user(
                email="testuser2@example.com",
                password="password123",
                nickname="testuser2",
                phone_number="01022222222",
                name="Test User 2",
                gender="F",
                birthday="2000-01-02",
            )
            study_group = await StudyGroup.objects.acreate(
                name="Test Study Group",
                max_headcount=10,
                start_at="2025-10-21T10:00:00Z",
                end_at="2025-11-21T10:00:00Z",
            )
            await GroupMember.objects.acreate(study_group=study_group, user=user1, is_leader=True)
            await GroupMember.objects.acreate(study_group=study_group, user=user2)

            communicator1 = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f"/ws/study-groups/{study_group.id}/chat/",
            )
            communicator1.scope["user"] = user1
            connected1, _ = await communicator1.connect()
            self.assertTrue(connected1)

            communicator2 = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f"/ws/study-groups/{study_group.id}/chat/",
            )
            communicator2.scope["user"] = user2
            connected2, _ = await communicator2.connect()
            self.assertTrue(connected2)

            # User1 sends initial message
            initial_content = "Initial message."
            await communicator1.send_json_to({"type": "chat.message", "content": initial_content})
            response = await communicator1.receive_json_from()
            message_id = response["message_id"]

            # User2 tries to edit User1's message
            new_content = "Edited by User2."
            await communicator2.send_json_to({"type": "chat.edit_message", "message_id": message_id, "new_content": new_content})
            error_response = await communicator2.receive_json_from()

            self.assertEqual(error_response["type"], "error")
            self.assertEqual(error_response["code"], "NOT_MESSAGE_SENDER")

            # Verify message in DB is unchanged
            original_message = await ChatMessage.objects.aget(id=message_id)
            self.assertEqual(original_message.content, initial_content)

            await communicator1.disconnect()
            await communicator2.disconnect()

        asyncio.run(_async_test_logic())

    def test_edit_message_not_found(self) -> None:
        """
        Tests that an error is returned when trying to edit a non-existent message.
        """

        async def _async_test_logic() -> None:
            user1 = await User.objects.acreate_user(
                email="testuser1@example.com",
                password="password123",
                nickname="testuser1",
                phone_number="01011111111",
                name="Test User 1",
                gender="M",
                birthday="2000-01-01",
            )
            study_group = await StudyGroup.objects.acreate(
                name="Test Study Group",
                max_headcount=10,
                start_at="2025-10-21T10:00:00Z",
                end_at="2025-11-21T10:00:00Z",
            )
            await GroupMember.objects.acreate(study_group=study_group, user=user1, is_leader=True)

            communicator1 = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f"/ws/study-groups/{study_group.id}/chat/",
            )
            communicator1.scope["user"] = user1
            connected, _ = await communicator1.connect()
            self.assertTrue(connected)

            # Try to edit a non-existent message
            non_existent_message_id = 99999
            new_content = "Edited content."
            await communicator1.send_json_to({"type": "chat.edit_message", "message_id": non_existent_message_id, "new_content": new_content})
            error_response = await communicator1.receive_json_from()

            self.assertEqual(error_response["type"], "error")
            self.assertEqual(error_response["code"], "MESSAGE_NOT_FOUND")

            await communicator1.disconnect()

        asyncio.run(_async_test_logic())
