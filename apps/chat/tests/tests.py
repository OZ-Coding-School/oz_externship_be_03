# apps/chat/tests/tests.py
from channels.testing import WebsocketCommunicator  # type: ignore[import-untyped]
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.chat.consumers import ChatConsumer
from apps.chat.models.chat_message import ChatMessage
from apps.studies.models.groups import GroupMember, StudyGroup

User = get_user_model()

class ChatConsumerTest(TestCase):
    # Django의 테스트 러너는 `async def test_...` 메소드를 직접 실행
    async def test_group_member_can_connect_and_send_message(self) -> None:
        """
        스터디 그룹 멤버가 웹소켓에 연결하고 메시지를 보냈을 때,
        해당 메시지가 DB에 저장되고 다시 클라이언트에게 전송되는지 테스트
        """
        # 1. 테스트 데이터 생성 (그룹 멤버)
        user = await User.objects.acreate_user(  # type: ignore[attr-defined]
            email="testuser@example.com",
            password="password123",
            nickname="testuser",
            phone_number="01012345678",
            name="Test User",
            gender="M",
            birthday="2000-01-01",
        )
        study_group = await StudyGroup.objects.acreate(
            name="Test Study Group",
            max_headcount=10,
            start_at="2025-10-21T10:00:00Z",
            end_at="2025-11-21T10:00:00Z",
        )
        await GroupMember.objects.acreate(study_group=study_group, user=user, is_leader=True)

        # 2. 웹소켓 커뮤니케이터 설정
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/study-groups/{study_group.id}/chat/")
        communicator.scope["user"] = user

        # 3. 웹소켓 연결 (성공해야 함)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # 4. 테스트 메시지 전송
        test_message_content = "Hello, this is a test message."
        await communicator.send_json_to({"type": "chat.message", "content": test_message_content})

        # 5. 방송된 메시지 확인
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "chat.message")
        self.assertEqual(response["message"], test_message_content)
        self.assertEqual(response["sender_id"], user.id)

        # 6. 메시지가 DB에 저장되었는지 확인
        message_exists = await ChatMessage.objects.filter(
            study_group=study_group, sender=user, content=test_message_content
        ).aexists()
        self.assertTrue(message_exists)

        # 7. 웹소켓 연결 종료
        await communicator.disconnect()

    async def test_non_group_member_is_rejected(self) -> None:
        """
        스터디 그룹 멤버가 아닌 사용자의 웹소켓 연결 시도가 거부되는지 테스트
        """
        # 1. 테스트 데이터 생성 (그룹 멤버가 아닌 유저)
        non_member_user = await User.objects.acreate_user(  # type: ignore[attr-defined]
            email="nonmember@example.com",
            password="password123",
            nickname="nonmember",
            phone_number="01087654321",
            name="Non Member",
            gender="F",
            birthday="2000-01-02",
        )
        study_group = await StudyGroup.objects.acreate(
            name="Another Test Group",
            max_headcount=5,
            start_at="2025-12-01T10:00:00Z",
            end_at="2025-12-31T10:00:00Z",
        )
        # 중요: non_member_user를 study_group에 추가하지 않음

        # 2. 웹소켓 커뮤니케이터 설정
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/study-groups/{study_group.id}/chat/")
        communicator.scope["user"] = non_member_user

        # 3. 웹소켓 연결 (실패해야 함)
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
