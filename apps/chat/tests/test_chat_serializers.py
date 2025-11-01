from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.chat.models import ChatMessage, LastReadMessage
from apps.chat.serializers import ChatMessageSerializer
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class ChatMessageSerializerTest(TestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            name="Test User",
            nickname="TestUser",
            phone_number="01012345678",
            gender="M",
            birthday="2000-01-01",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@test.com",
            password="testpass123",
            name="Other User",
            nickname="OtherUser",
            phone_number="01087654321",
            gender="F",
            birthday="2000-01-01",
        )
        self.study_group = StudyGroup.objects.create(
            name="Test Study Group",
            introduction="Test Description",
            max_headcount=5,
            start_at="2025-01-01",
            end_at="2025-12-31",
        )
        GroupMember.objects.create(study_group=self.study_group, user=self.user, is_leader=True)
        self.message1 = ChatMessage.objects.create(study_group=self.study_group, sender=self.user, content="Message 1")
        self.message2 = ChatMessage.objects.create(
            study_group=self.study_group, sender=self.other_user, content="Message 2"
        )
        self.message3 = ChatMessage.objects.create(study_group=self.study_group, sender=self.user, content="Message 3")

    def test_get_is_read_unauthenticated_user(self) -> None:
        """정상: 비인증 사용자는 항상 is_read가 False"""
        request = self.factory.get("/")
        serializer = ChatMessageSerializer(instance=self.message1, context={"request": request})
        self.assertFalse(serializer.data["is_read"])

    def test_get_is_read_no_last_read_message(self) -> None:
        """정상: 마지막 읽은 메시지 기록이 없는 경우 is_read가 False"""
        request = self.factory.get("/")
        request.user = self.user
        serializer = ChatMessageSerializer(instance=self.message1, context={"request": request})
        self.assertFalse(serializer.data["is_read"])

    def test_get_is_read_message_is_read(self) -> None:
        """정상: 메시지가 읽은 상태인 경우 is_read가 True"""
        LastReadMessage.objects.create(
            user=self.user, study_group=self.study_group, message=self.message2  # message2까지 읽음
        )
        request = self.factory.get("/")
        request.user = self.user

        serializer = ChatMessageSerializer(instance=self.message1, context={"request": request})
        self.assertTrue(serializer.data["is_read"])

        serializer = ChatMessageSerializer(instance=self.message2, context={"request": request})
        self.assertTrue(serializer.data["is_read"])

    def test_get_is_read_message_is_not_read(self) -> None:
        """정상: 메시지가 읽지 않은 상태인 경우 is_read가 False"""
        LastReadMessage.objects.create(
            user=self.user, study_group=self.study_group, message=self.message2  # message2까지 읽음
        )
        request = self.factory.get("/")
        request.user = self.user

        serializer = ChatMessageSerializer(instance=self.message3, context={"request": request})
        self.assertFalse(serializer.data["is_read"])

    def test_get_file_url_is_none(self) -> None:
        """get_file_url 메서드가 항상 None을 반환하는지 테스트"""
        serializer = ChatMessageSerializer(instance=self.message1)
        self.assertIsNone(serializer.data["file_url"])

    def test_get_is_read_no_request_in_context(self) -> None:
        """컨텍스트에 request가 없을 때 get_is_read가 False를 반환하는지 테스트"""
        serializer = ChatMessageSerializer(instance=self.message1, context={})
        self.assertFalse(serializer.data["is_read"])


class LastMessageSerializerTest(TestCase):
    def test_serialization(self) -> None:
        from datetime import datetime

        from apps.chat.serializers import LastMessageSerializer

        data = {
            "last_message_content": "Hello World",
            "last_message_sender_nickname": "TestUser",
            "last_message_created_at": datetime(2025, 1, 1, 10, 0, 0),
        }
        serializer = LastMessageSerializer(data)
        self.assertEqual(serializer.data["last_message_content"], "Hello World")
        self.assertEqual(serializer.data["last_message_sender_nickname"], "TestUser")
        self.assertIn("2025-01-01T10:00:00Z", serializer.data["last_message_created_at"])


class ChatRoomSerializerTest(TestCase):
    def test_serialization(self) -> None:
        from datetime import datetime

        from apps.chat.serializers import ChatRoomSerializer

        data = {
            "id": 1,
            "name": "Test Group",
            "last_message_content": "Last message content",
            "last_message_sender_nickname": "Sender Nickname",
            "last_message_created_at": datetime(2025, 1, 1, 12, 0, 0),
            "unread_count": 5,
        }
        serializer = ChatRoomSerializer(data)
        self.assertEqual(serializer.data["id"], 1)
        self.assertEqual(serializer.data["name"], "Test Group")
        self.assertEqual(serializer.data["last_message"]["last_message_content"], "Last message content")
        self.assertEqual(serializer.data["last_message"]["last_message_sender_nickname"], "Sender Nickname")
        self.assertIn("2025-01-01T12:00:00Z", serializer.data["last_message"]["last_message_created_at"])
        self.assertEqual(serializer.data["unread_count"], 5)

    def test_serialization_no_last_message(self) -> None:
        from apps.chat.serializers import ChatRoomSerializer

        data = {
            "id": 2,
            "name": "Empty Group",
            "last_message_content": None,
            "last_message_sender_nickname": None,
            "last_message_created_at": None,
            "unread_count": 0,
        }
        serializer = ChatRoomSerializer(data)
        self.assertEqual(serializer.data["id"], 2)
        self.assertEqual(serializer.data["name"], "Empty Group")
        self.assertIsNone(serializer.data["last_message"]["last_message_content"])
        self.assertIsNone(serializer.data["last_message"]["last_message_sender_nickname"])
        self.assertIsNone(serializer.data["last_message"]["last_message_created_at"])
        self.assertEqual(serializer.data["unread_count"], 0)


class ChatMessageModelTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            name="Test User",
            nickname="TestUser",
            phone_number="01012345678",
            gender="M",
            birthday="2000-01-01",
        )
        self.study_group = StudyGroup.objects.create(
            name="Test Study Group",
            introduction="Test Description",
            max_headcount=5,
            start_at="2025-01-01",
            end_at="2025-12-31",
        )
        self.message = ChatMessage.objects.create(
            study_group=self.study_group, sender=self.user, content="This is a test message."
        )

    def test_chat_message_str_representation(self) -> None:
        """ChatMessage 모델의 __str__ 메서드가 올바른 형식의 문자열을 반환하는지 테스트"""
        expected_str = f"{self.user.nickname}: {self.message.content[:20]}"
        self.assertEqual(str(self.message), expected_str)

    def test_chat_message_str_with_no_sender(self) -> None:
        """ChatMessage 모델의 sender가 없을 때 __str__ 메서드가 올바르게 동작하는지 테스트"""
        self.message.sender = None
        self.message.save()
        expected_str = f"알 수 없는 사용자: {self.message.content[:20]}"
        self.assertEqual(str(self.message), expected_str)


class LastReadMessageModelTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            name="Test User",
            nickname="TestUser",
            phone_number="01012345678",
            gender="M",
            birthday="2000-01-01",
        )
        self.study_group = StudyGroup.objects.create(
            name="Test Study Group",
            introduction="Test Description",
            max_headcount=5,
            start_at="2025-01-01",
            end_at="2025-12-31",
        )
        self.message = ChatMessage.objects.create(
            study_group=self.study_group, sender=self.user, content="This is a test message."
        )
        self.last_read_message = LastReadMessage.objects.create(
            study_group=self.study_group, user=self.user, message=self.message
        )

    def test_last_read_message_str_representation(self) -> None:
        """LastReadMessage 모델의 __str__ 메서드가 올바른 형식의 문자열을 반환하는지 테스트"""
        expected_str = f"{self.user} last read {self.message.id}"
        self.assertEqual(str(self.last_read_message), expected_str)
