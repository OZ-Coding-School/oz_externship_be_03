from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.chat.models import ChatMessage, LastReadMessage
from apps.chat.services.chat_room_service import ChatRoomService
from apps.studies.models.groups import GroupMember, StudyGroup

User = get_user_model()


class ChatRoomServiceTest(TestCase):
    def setUp(self) -> None:
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            password="password123",
            nickname="user1",
            phone_number="01011112222",
            name="User One",
            gender="M",
            birthday="2000-01-01",
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            password="password123",
            nickname="user2",
            phone_number="01033334444",
            name="User Two",
            gender="F",
            birthday="2000-01-02",
        )
        self.study_group1 = StudyGroup.objects.create(
            name="Test Study Group 1",
            max_headcount=10,
            start_at="2025-01-01T00:00:00Z",
            end_at="2025-12-31T23:59:59Z",
        )
        GroupMember.objects.create(user=self.user1, study_group=self.study_group1, is_leader=True)
        self.msg1_sg1 = ChatMessage.objects.create(
            sender=self.user1, study_group=self.study_group1, content="Hello SG1"
        )

    def test_get_chat_rooms_for_user_no_messages(self) -> None:
        """메시지가 없는 채팅방의 경우 last_message 관련 필드가 None이어야 합니다."""
        study_group2 = StudyGroup.objects.create(
            name="Test Study Group 2",
            max_headcount=10,
            start_at="2025-01-01T00:00:00Z",
            end_at="2025-12-31T23:59:59Z",
        )
        GroupMember.objects.create(user=self.user1, study_group=study_group2, is_leader=True)

        chat_rooms = ChatRoomService.get_chat_rooms_for_user(self.user1)
        chat_rooms_list = list(chat_rooms)

        sg2_data = next((room for room in chat_rooms_list if room["id"] == study_group2.id), None)
        self.assertIsNotNone(sg2_data)
        assert sg2_data is not None
        self.assertIsNone(sg2_data["last_message_content"])
        self.assertIsNone(sg2_data["last_message_sender_nickname"])

    def test_get_chat_rooms_for_user_all_messages_read(self) -> None:
        """모든 메시지를 읽었을 때 unread_count가 0이어야 합니다."""
        LastReadMessage.objects.create(user=self.user1, study_group=self.study_group1, message=self.msg1_sg1)

        chat_rooms = ChatRoomService.get_chat_rooms_for_user(self.user1)
        chat_rooms_list = list(chat_rooms)

        sg1_data = next((room for room in chat_rooms_list if room["id"] == self.study_group1.id), None)
        self.assertIsNotNone(sg1_data)
        assert sg1_data is not None
        self.assertEqual(sg1_data["unread_count"], 0)

    def test_get_chat_rooms_for_user_not_member(self) -> None:
        """사용자가 어떤 스터디 그룹의 멤버도 아닌 경우 빈 목록을 반환합니다."""
        chat_rooms = ChatRoomService.get_chat_rooms_for_user(self.user2)
        chat_rooms_list = list(chat_rooms)
        self.assertEqual(len(chat_rooms_list), 0)
