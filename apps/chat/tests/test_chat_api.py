from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatMessage, LastReadMessage
from apps.chat.services.chat_room_service import ChatRoomService
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
        messages_to_create = [
            ChatMessage(
                sender=self.user1,
                study_group=self.study_group,
                content=f"Message {i}",
            )
            for i in range(1, 351)
        ]
        ChatMessage.objects.bulk_create(messages_to_create)

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
        self.assertEqual(len(response.data["results"]), 300)
        self.assertEqual(response.data["count"], 350)

    def test_message_list_success_second_page_100_messages(self) -> None:
        """두 번째 페이지 요청 시 100개의 메시지를 반환합니다."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url + "?page=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 100)  # Remaining 100 messages

    def test_message_list_is_read_status(self) -> None:
        """메시지 읽음 상태를 올바르게 반환합니다."""
        # user1이 메시지 300까지 읽었다고 가정
        last_read_message = ChatMessage.objects.get(content="Message 300")
        LastReadMessage.objects.create(user=self.user1, study_group=self.study_group, message=last_read_message)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        messages = response.data["results"]
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
        messages = response.data["results"]
        # 첫 번째 메시지 (가장 최근 메시지)의 발신자 닉네임 확인
        self.assertEqual(messages[0]["sender_nickname"], self.user1.nickname)

    def test_message_list_is_read_status_no_last_read(self) -> None:
        """마지막으로 읽은 메시지가 없을 때 is_read가 False인지 확인합니다."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        messages = response.data["results"]
        for msg in messages:
            self.assertFalse(msg["is_read"])

    def test_message_list_no_pagination(self) -> None:
        """페이지네이션이 비활성화되었을 때, 모든 메시지를 리스트로 반환하는지 테스트합니다."""
        from apps.chat.views import ChatMessageListView

        # Temporarily disable pagination for this test
        original_pagination_class = ChatMessageListView.pagination_class
        ChatMessageListView.pagination_class = None  # type: ignore

        try:
            self.client.force_authenticate(user=self.user1)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsInstance(response.data, list)
            self.assertEqual(len(response.data), 350)

        finally:
            # Restore original pagination class to avoid affecting other tests
            ChatMessageListView.pagination_class = original_pagination_class


class ChatRoomServiceTest(APITestCase):
    def setUp(self) -> None:
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            password="password123",
            nickname="user1",
            name="User One",
            phone_number="01011112222",
            gender="M",
            birthday="2000-01-01",
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            password="password123",
            nickname="user2",
            name="User Two",
            phone_number="01033334444",
            gender="F",
            birthday="2000-01-02",
        )
        self.study_group1 = StudyGroup.objects.create(
            name="Group 1", max_headcount=10, start_at="2025-01-01T00:00:00Z", end_at="2025-12-31T23:59:59Z"
        )
        self.study_group2 = StudyGroup.objects.create(
            name="Group 2", max_headcount=10, start_at="2025-01-01T00:00:00Z", end_at="2025-12-31T23:59:59Z"
        )
        self.study_group3 = StudyGroup.objects.create(
            name="Group 3", max_headcount=10, start_at="2025-01-01T00:00:00Z", end_at="2025-12-31T23:59:59Z"
        )  # For no messages case

        GroupMember.objects.create(user=self.user1, study_group=self.study_group1, is_leader=True)
        GroupMember.objects.create(user=self.user2, study_group=self.study_group1)
        GroupMember.objects.create(user=self.user1, study_group=self.study_group2, is_leader=True)
        GroupMember.objects.create(user=self.user1, study_group=self.study_group3)

        # Messages for Group 1
        msg1_g1 = ChatMessage.objects.create(sender=self.user1, study_group=self.study_group1, content="G1 Msg 1")
        ChatMessage.objects.create(sender=self.user2, study_group=self.study_group1, content="G1 Msg 2")

        # Messages for Group 2
        ChatMessage.objects.create(sender=self.user1, study_group=self.study_group2, content="G2 Msg 1")

        # User1 has read up to msg1_g1 in Group 1
        LastReadMessage.objects.create(user=self.user1, study_group=self.study_group1, message=msg1_g1)

    def test_get_chat_rooms_for_user_success(self) -> None:
        """서비스가 채팅방 목록, 마지막 메시지, 안 읽은 수를 정확히 반환하는지 테스트합니다."""
        chat_rooms = list(ChatRoomService.get_chat_rooms_for_user(self.user1))

        # Should return 3 rooms for user1
        self.assertEqual(len(chat_rooms), 3)

        sorted_rooms = sorted(chat_rooms, key=lambda x: x["name"])

        # Assertions for Group 1
        room1 = sorted_rooms[0]
        self.assertEqual(room1["name"], "Group 1")
        self.assertEqual(room1["last_message_content"], "G1 Msg 2")
        self.assertEqual(room1["last_message_sender_nickname"], self.user2.nickname)
        self.assertEqual(room1["unread_count"], 1)

        # Assertions for Group 2
        room2 = sorted_rooms[1]
        self.assertEqual(room2["name"], "Group 2")
        self.assertEqual(room2["last_message_content"], "G2 Msg 1")
        self.assertEqual(room2["last_message_sender_nickname"], self.user1.nickname)
        self.assertEqual(room2["unread_count"], 1)  # No last read message, so all are unread

        # Assertions for Group 3 (no messages)
        room3 = sorted_rooms[2]
        self.assertEqual(room3["name"], "Group 3")
        self.assertIsNone(room3["last_message_content"])
        self.assertIsNone(room3["last_message_sender_nickname"])
        self.assertEqual(room3["unread_count"], 0)
