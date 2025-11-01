from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from rest_framework.request import Request

from apps.chat.models import ChatMessage, LastReadMessage
from apps.chat.serializers import ChatMessageSerializer
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class ChatMessageSerializerTest(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="user1@example.com",
            password="password123",
            nickname="user1",
            phone_number="01011112222",
            name="User One",
            gender="M",
            birthday="2000-01-01",
        )
        self.study_group = StudyGroup.objects.create(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-01-01T00:00:00Z",
            end_at="2025-12-31T23:59:59Z",
        )
        GroupMember.objects.create(user=self.user, study_group=self.study_group, is_leader=True)
        self.message = ChatMessage.objects.create(
            sender=self.user,
            study_group=self.study_group,
            content="Test Message",
        )

    def test_is_read_without_request_context(self) -> None:
        """request가 context에 없으면 is_read는 False여야 합니다."""
        serializer = ChatMessageSerializer(self.message, context={})
        self.assertFalse(serializer.data["is_read"])

    def test_is_read_with_unauthenticated_user(self) -> None:
        """비인증 사용자의 경우 is_read는 False여야 합니다."""
        request = self.factory.get("/")
        request.user = AnonymousUser()
        serializer = ChatMessageSerializer(self.message, context={"request": Request(request)})
        self.assertFalse(serializer.data["is_read"])

    def test_is_read_without_last_read_message(self) -> None:
        """LastReadMessage가 없으면 is_read는 False여야 합니다."""
        request = self.factory.get("/")
        request.user = self.user
        serializer = ChatMessageSerializer(self.message, context={"request": Request(request)})
        self.assertFalse(serializer.data["is_read"])

    def test_is_read_when_message_is_read(self) -> None:
        """메시지를 읽었을 때 is_read는 True여야 합니다."""
        LastReadMessage.objects.create(user=self.user, study_group=self.study_group, message=self.message)
        request = self.factory.get("/")
        request.user = self.user
        serializer = ChatMessageSerializer(self.message, context={"request": Request(request)})
        self.assertTrue(serializer.data["is_read"])
