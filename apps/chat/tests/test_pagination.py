from django.test import RequestFactory, TestCase
from rest_framework.request import Request

from apps.chat.models import ChatMessage
from apps.chat.pagination import ChatMessagePagination
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class ChatMessagePaginationTest(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.pagination = ChatMessagePagination()
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
        for i in range(350):
            ChatMessage.objects.create(
                sender=self.user,
                study_group=self.study_group,
                content=f"Message {i}",
            )
        self.queryset = ChatMessage.objects.all().order_by("-created_at")

    def test_second_page_returns_100_messages(self) -> None:
        """두 번째 페이지는 100개 메시지 반환"""
        request = self.factory.get("/messages/", {"page": "2"})

        # DRF의 Request 객체로 변환
        drf_request = Request(request)

        result = self.pagination.paginate_queryset(self.queryset, drf_request)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 50)  # 350개 중 첫 페이지 300개 이후 남은 50개
        self.assertEqual(self.pagination.page_size, 100)
