from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup

User = get_user_model()


class ChatRoomAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.user1 = User.objects.create_user(
            email="user1@test.com",
            password="password123",
            nickname="user1",
            birthday="2000-01-01",
            gender="M",
            phone_number="01011112222",
        )
        self.user2 = User.objects.create_user(
            email="user2@test.com",
            password="password123",
            nickname="user2",
            birthday="2000-01-01",
            gender="F",
            phone_number="01033334444",
        )

        # Case 1: user1, user2가 속한 그룹 (메시지 3개)
        self.study_group1 = StudyGroup.objects.create(
            name="Test Group 1",
            start_at=timezone.make_aware(datetime(2025, 1, 1, 0, 0, 0)),
            end_at=timezone.make_aware(datetime(2025, 1, 8, 0, 0, 0)),
        )
        GroupMember.objects.create(study_group=self.study_group1, user=self.user1, is_leader=True)
        GroupMember.objects.create(study_group=self.study_group1, user=self.user2)
        self.msg1 = ChatMessage.objects.create(study_group=self.study_group1, sender=self.user1, content="Hello")
        self.msg2 = ChatMessage.objects.create(study_group=self.study_group1, sender=self.user2, content="Hi")
        self.msg3 = ChatMessage.objects.create(study_group=self.study_group1, sender=self.user1, content="Test")

        # Case 2: user1만 속한 그룹 (메시지 없음)
        self.study_group2 = StudyGroup.objects.create(
            name="Test Group 2",
            start_at=timezone.make_aware(datetime(2025, 1, 1, 0, 0, 0)),
            end_at=timezone.make_aware(datetime(2025, 1, 8, 0, 0, 0)),
        )
        GroupMember.objects.create(study_group=self.study_group2, user=self.user1, is_leader=True)

        # Case 3: user1이 속한 또 다른 그룹 (메시지 2개)
        self.study_group3 = StudyGroup.objects.create(
            name="Test Group 3",
            start_at=timezone.make_aware(datetime(2025, 1, 1, 0, 0, 0)),
            end_at=timezone.make_aware(datetime(2025, 1, 8, 0, 0, 0)),
        )

        self.client.force_authenticate(user=self.user1)

    def test_get_chat_room_list_success(self) -> None:
        url = reverse("chat:room-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # user1은 2개의 그룹에 속해 있음

        # 응답 순서는 생성 역순일 수 있으므로 이름으로 찾아서 확인
        room1_data = next((r for r in response.data if r["name"] == "Test Group 1"), None)
        room2_data = next((r for r in response.data if r["name"] == "Test Group 2"), None)
        room3_data = next((r for r in response.data if r["name"] == "Test Group 3"), None)

        assert room1_data is not None
        assert room1_data["last_message"] is not None
        self.assertEqual(room1_data["last_message"]["content"], self.msg3.content)
        assert self.msg3.sender is not None  # mypy: sender can be None
        self.assertEqual(room1_data["last_message"]["sender_nickname"], self.msg3.sender.nickname)
        self.assertIsNotNone(room1_data["last_message"]["created_at"])

    def test_get_chat_room_list_unauthenticated(self) -> None:
        """채팅방 목록 조회 API 비인증 유저 테스트"""
        self.client.logout()
        url = reverse("chat:room-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_room_with_no_messages(self) -> None:
        """메시지가 없는 채팅방의 last_message는 null이어야 함"""
        url = reverse("chat:room-list")
        response = self.client.get(url)
        room2_data = next((r for r in response.data if r["name"] == "Test Group 2"), None)

        assert room2_data is not None
        self.assertIsNone(room2_data["last_message"])

    def test_unread_count_with_no_read_history(self) -> None:
        """읽은 기록이 없을 때, 모든 메시지가 안 읽은 것으로 계산되어야 함"""
        url = reverse("chat:room-list")
        response = self.client.get(url)
        room1_data = next((r for r in response.data if r["name"] == "Test Group 1"), None)

        assert room1_data is not None
        self.assertEqual(room1_data["unread_message_count"], 3)

    def test_unread_count_with_some_messages_read(self) -> None:
        """일부 메시지를 읽었을 때, 안 읽은 메시지 수가 정확해야 함"""
        # user1이 group1에서 msg2까지 읽음
        LastReadMessage.objects.create(study_group=self.study_group1, user=self.user1, message=self.msg2)

        url = reverse("chat:room-list")
        response = self.client.get(url)
        room1_data = next((r for r in response.data if r["name"] == "Test Group 1"), None)

        assert room1_data is not None
        self.assertEqual(room1_data["unread_message_count"], 1)  # msg3만 안 읽음

    def test_unread_count_with_all_messages_read(self) -> None:
        """모든 메시지를 읽었을 때, 안 읽은 메시지 수는 0이어야 함"""
        # user1이 group1에서 msg3(마지막)까지 읽음
        LastReadMessage.objects.create(study_group=self.study_group1, user=self.user1, message=self.msg3)

        url = reverse("chat:room-list")
        response = self.client.get(url)
        room1_data = next((r for r in response.data if r["name"] == "Test Group 1"), None)

        assert room1_data is not None
        self.assertEqual(room1_data["unread_message_count"], 0)
