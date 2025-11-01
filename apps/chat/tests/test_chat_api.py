from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup

User = get_user_model()


class ChatMessageListAPIViewTest(APITestCase):
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
        self.study_group = StudyGroup.objects.create(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-01-01T00:00:00Z",
            end_at="2025-12-31T23:59:59Z",
        )
        self.group_member1 = GroupMember.objects.create(user=self.user1, study_group=self.study_group, is_leader=True)
        self.group_member2 = GroupMember.objects.create(user=self.user2, study_group=self.study_group)

        # Create 350 messages for pagination testing
        for i in range(1, 351):
            ChatMessage.objects.create(
                sender=self.user1,
                study_group=self.study_group,
                content=f"Message {i}",
            )

        self.url = reverse("chat:message-list", kwargs={"study_group_id": self.study_group.id})

    def test_message_list_unauthenticated(self) -> None:
        """인증되지 않은 사용자는 메시지 목록을 조회할 수 없습니다."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_message_list_not_group_member(self) -> None:
        """스터디 그룹 멤버가 아닌 사용자는 메시지 목록을 조회할 수 없습니다."""
        non_member = User.objects.create_user(
            email="nonmember@example.com",
            password="password123",
            nickname="nonmember",
            phone_number="01055556666",
            name="Non Member",
            gender="M",
            birthday="2000-01-03",
        )
        self.client.force_authenticate(user=non_member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_message_list_success_first_page_300_messages(self) -> None:
        """첫 페이지 요청 시 300개의 메시지를 반환합니다."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["messages"]), 300)
        self.assertEqual(response.data["data"]["pagination"]["page"], 1)
        self.assertEqual(response.data["data"]["pagination"]["page_size"], 300)
        self.assertEqual(response.data["data"]["pagination"]["total_count"], 350)

    def test_message_list_success_second_page_100_messages(self) -> None:
        """두 번째 페이지 요청 시 100개의 메시지를 반환합니다."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url + "?page=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["messages"]), 50)  # Remaining 50 messages
        self.assertEqual(response.data["data"]["pagination"]["page"], 2)
        self.assertEqual(response.data["data"]["pagination"]["page_size"], 100)
        self.assertEqual(response.data["data"]["pagination"]["total_count"], 350)

    def test_message_list_is_read_status(self) -> None:
        """메시지 읽음 상태를 올바르게 반환합니다."""
        # user1이 메시지 300까지 읽었다고 가정
        last_read_message = ChatMessage.objects.get(content="Message 300")
        LastReadMessage.objects.create(user=self.user1, study_group=self.study_group, message=last_read_message)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        messages = response.data["data"]["messages"]
        # 메시지 300까지는 is_read가 True여야 함
        for msg in messages:
            if int(msg["content"].split()[-1]) <= 300:
                self.assertTrue(msg["is_read"])
            else:
                self.assertFalse(msg["is_read"])

    def test_message_list_sender_nickname(self) -> None:
        """메시지 발신자의 닉네임을 올바르게 반환합니다."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        messages = response.data["data"]["messages"]
        # 첫 번째 메시지 (가장 최근 메시지)의 발신자 닉네임 확인
        self.assertEqual(messages[0]["sender_nickname"], self.user1.nickname)

    def test_message_list_pagination_logic(self) -> None:
        """페이지네이션 로직이 올바르게 동작하는지 테스트합니다."""
        self.client.force_authenticate(user=self.user1)
        # page=1일 때 300개 메시지 반환
        response = self.client.get(self.url + "?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["messages"]), 300)
        self.assertEqual(response.data["data"]["pagination"]["page"], 1)

        # page=2일 때 100개 메시지 반환 (남은 50개)
        response = self.client.get(self.url + "?page=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["messages"]), 50)
        self.assertEqual(response.data["data"]["pagination"]["page"], 2)

    def test_message_list_pagination_none_fallback(self) -> None:
        """페이지네이션 클래스가 None일 때 ListAPIView의 기본 동작을 테스트합니다."""
        self.client.force_authenticate(user=self.user1)
        with patch("apps.chat.views.ChatMessageListView.pagination_class", None):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsInstance(response.data, list)
            self.assertEqual(len(response.data), 350)


class ChatRoomListAPIViewTest(APITestCase):
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
        self.study_group1 = StudyGroup.objects.create(
            name="Test Study Group 1",
            max_headcount=10,
            start_at="2025-01-01T00:00:00Z",
            end_at="2025-12-31T23:59:59Z",
        )
        GroupMember.objects.create(user=self.user1, study_group=self.study_group1, is_leader=True)
        self.url = reverse("chat:room-list")

    @patch("apps.chat.views.ChatRoomService.get_chat_rooms_for_user")
    def test_get_chat_room_list_authenticated(self, mock_get_chat_rooms: Mock) -> None:
        """인증된 사용자는 채팅방 목록을 조회할 수 있습니다."""
        mock_get_chat_rooms.return_value = [
            {
                "id": self.study_group1.id,
                "name": self.study_group1.name,
                "last_message_content": "last message",
                "last_message_sender_nickname": "sender",
                "last_message_created_at": "2025-11-01T00:00:00Z",
                "unread_count": 1,
            }
        ]
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], self.study_group1.name)
        mock_get_chat_rooms.assert_called_once_with(self.user1)

    def test_get_chat_room_list_empty(self) -> None:
        """참여 중인 채팅방이 없는 경우 빈 목록을 반환합니다."""
        user_no_group = User.objects.create_user(
            email="nogroup@example.com",
            password="password123",
            nickname="nogroup",
            phone_number="01077778888",
            name="No Group User",
            gender="F",
            birthday="2000-01-04",
        )
        self.client.force_authenticate(user=user_no_group)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
