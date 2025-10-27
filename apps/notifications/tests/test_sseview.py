import asyncio
import json
from datetime import date
from typing import AsyncGenerator, Dict, Any, AsyncIterator, cast
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.notifications.views.SSE_views import notification_stream
from apps.users.enums import Gender

User = get_user_model()


class SSEViewsTest(IsolatedRedisTestClient):
    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()

        # 테스트 사용자들 생성
        self.user = User.objects.create_user(
            email="user@test.com",
            password="test123",
            nickname="testuser",
            name="테스트유저",
            phone_number="010-1111-2222",
            birthday=date(1990, 1, 1),
            gender=Gender.MALE
        )

        self.other_user = User.objects.create_user(
            email="user2@test.com",
            password="test123",
            nickname="otheruser",
            name="다른유저",
            phone_number="010-3333-4444",
            birthday=date(1992, 5, 15),
            gender=Gender.FEMALE
        )

    async def test_sse_connection_authenticated_user(self) -> None:
        """인증된 사용자의 SSE 연결 테스트"""
        request = self.factory.get(f'/notifications/sse/{self.user.id}/')
        request.user = self.user

        response = await notification_stream(request, self.user.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertEqual(response['Connection'], 'keep-alive')

    async def test_sse_connection_unauthorized_user(self) -> None:
        """다른 사용자 채널 접근 차단 테스트"""
        request = self.factory.get(f'/notifications/sse/{self.other_user.id}/')
        request.user = self.user  # 다른 사용자로 접근 시도

        response = await notification_stream(request, self.other_user.id)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'text/event-stream')

    async def test_sse_connection_unauthenticated(self) -> None:
        """비인증 사용자 접근 차단 테스트"""
        from django.contrib.auth.models import AnonymousUser
        
        request = self.factory.get(f'/notifications/sse/{self.user.id}/')
        request.user = AnonymousUser()

        response = await notification_stream(request, self.user.id)

        # 수동 인증 체크에 의한 401
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'], 'text/event-stream')


    @patch('apps.notifications.services.redis_pubsub_classify.notification_pubsub.subscribe_user_notification')
    async def test_notification_stream_function_authorized(self, mock_subscribe: AsyncMock) -> None:
        """notification_stream 함수 직접 테스트 - 인증된 사용자"""
        # 가짜 알림 데이터
        mock_notifications = [
            {"id": 1, "type": "APPLICATION_CREATED", "content": "테스트 알림 1"},
            {"id": 2, "type": "APPLICATION_CREATED", "content": "테스트 알림 2"}
        ]

        async def fake_subscribe(user_id:int)->AsyncGenerator[Dict[str, Any], None]:
            for notification in mock_notifications:
                yield notification

        mock_subscribe.return_value = fake_subscribe(self.user.id)

        # 요청 생성
        request = self.factory.get(f'/notifications/sse/{self.user.id}/')
        request.user = self.user

        # 비동기 함수 실행
        response = await notification_stream(request, self.user.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertEqual(response['Connection'], 'keep-alive')

    async def test_notification_stream_function_unauthorized(self) -> None:
        """notification_stream 함수 직접 테스트 - 권한 없는 사용자"""
        request = self.factory.get(f'/notifications/sse/{self.other_user.id}/')
        request.user = self.user  # 다른 사용자로 접근 시도

        response = await notification_stream(request, self.other_user.id)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'text/event-stream')


    @patch('apps.notifications.services.redis_pubsub_classify.notification_pubsub.subscribe_user_notification')
    async def test_sse_stream_content_format(self, mock_subscribe: AsyncMock) -> None:
        """SSE 스트림 데이터 형식 테스트"""
        # 가짜 알림 데이터
        test_notification = {
            "id": 123,
            "type": "APPLICATION_CREATED",
            "content": "새로운 지원자가 지원했습니다.",
            "created_at": "2024-01-01T10:00:00Z",
            "is_read": False
        }

        async def fake_subscribe(user_id:int)->AsyncGenerator[Dict[str, Any], None]:
            yield test_notification

        mock_subscribe.return_value = fake_subscribe(self.user.id)

        request = self.factory.get(f'/notifications/sse/{self.user.id}/')
        request.user = self.user

        response = await notification_stream(request, self.user.id)

        # 스트리밍 응답 내용 확인
        content_list:list[str] = []
        streaming_content = cast(AsyncIterator[bytes],response.streaming_content)
        async for chunk in streaming_content:
            content_list.append(chunk.decode("utf-8"))

        # 연결 메시지 확인
        self.assertIn('data:{"type": "connected"}', content_list[0])

        # 알림 데이터 확인
        notification_chunk = content_list[1]
        self.assertIn(f'"id": {test_notification["id"]}', notification_chunk)
        self.assertIn(f'"content": "{test_notification["content"]}"', notification_chunk)


    @patch('apps.notifications.services.redis_pubsub_classify.notification_pubsub.subscribe_user_notification')
    async def test_sse_stream_exception_handling(self, mock_subscribe: AsyncMock) -> None:
        """SSE 스트림 예외 처리 테스트"""
        # Redis 구독에서 예외 발생 시뮬레이션
        async def fake_subscribe_with_error(user_id:int)->AsyncGenerator[Dict[str, Any], None]:
            yield {"id": 1, "content": "정상 알림"}
            raise Exception("Redis connection error")

        mock_subscribe.return_value = fake_subscribe_with_error(self.user.id)

        request = self.factory.get(f'/notifications/sse/{self.user.id}/')
        request.user = self.user

        response = await notification_stream(request, self.user.id)

        # 스트리밍 응답 내용 확인
        content_list:list[str] = []
        streaming_content = cast(AsyncIterator[bytes],response.streaming_content)
        async for chunk in streaming_content:
            content_list.append(chunk.decode("utf-8"))

        # 에러 메시지가 포함되어야 함
        error_found = False
        for content_chunk in content_list:
            if 'error' in content_chunk and 'Redis connection error' in content_chunk:
                error_found = True
                break

        self.assertTrue(error_found, "예외 상황에서 에러 메시지가 전송되어야 합니다")

    def test_sse_url_pattern(self) -> None:
        """SSE URL 패턴 테스트"""
        url = reverse('notifications:sse_stream', args=[123])
        self.assertEqual(url, '/notifications/sse/123/')

    async def test_sse_multiple_notifications(self) -> None:
        """다중 알림 스트리밍 테스트"""
        with patch('apps.notifications.services.redis_pubsub_classify.notification_pubsub.subscribe_user_notification') as mock_subscribe:
            # 여러 알림 시뮬레이션
            notifications = [
                {"id": 1, "content": "첫 번째 알림"},
                {"id": 2, "content": "두 번째 알림"},
                {"id": 3, "content": "세 번째 알림"}
            ]

            async def fake_multiple_subscribe(user_id:int)->AsyncGenerator[Dict[str, Any], None]:
                for notification in notifications:
                    yield notification

            mock_subscribe.return_value = fake_multiple_subscribe(self.user.id)

            request = self.factory.get(f'/notifications/sse/{self.user.id}/')
            request.user = self.user

            response = await notification_stream(request, self.user.id)

            content_list:list[str] = []
            streaming_content = cast(AsyncIterator[bytes],response.streaming_content)
            async for chunk in streaming_content:
                content_list.append(chunk.decode("utf-8"))

            # 연결 메시지 + 3개 알림 = 최소 4개 청크
            self.assertGreaterEqual(len(content_list), 4)

            # 각 알림이 포함되어 있는지 확인
            all_content = ''.join(content_list)
            for notification in notifications:
                self.assertIn(notification["content"], all_content)

    # 동기 테스트 래퍼들 - async 테스트를 동기로 실행
    def test_async_sse_connection_authenticated_user(self) -> None:
        """비동기 테스트 래퍼 - 인증된 사용자 SSE 연결"""
        asyncio.run(self.test_sse_connection_authenticated_user())

    def test_async_sse_connection_unauthorized_user(self) -> None:
        """비동기 테스트 래퍼 - 권한 없는 사용자 SSE 연결"""
        asyncio.run(self.test_sse_connection_unauthorized_user())

    def test_async_sse_connection_unauthenticated(self) -> None:
        """비동기 테스트 래퍼 - 비인증 사용자 SSE 연결"""
        asyncio.run(self.test_sse_connection_unauthenticated())

    def test_async_notification_stream_authorized(self) -> None:
        """비동기 테스트 래퍼 - 인증된 사용자"""
        asyncio.run(self.test_notification_stream_function_authorized())

    def test_async_notification_stream_unauthorized(self) -> None:
        """비동기 테스트 래퍼 - 권한 없는 사용자"""
        asyncio.run(self.test_notification_stream_function_unauthorized())

    def test_async_sse_stream_content_format(self) -> None:
        """비동기 테스트 래퍼 - 스트림 형식"""
        asyncio.run(self.test_sse_stream_content_format())

    def test_async_sse_stream_exception_handling(self) -> None:
        """비동기 테스트 래퍼 - 예외 처리"""
        asyncio.run(self.test_sse_stream_exception_handling())

    def test_async_sse_multiple_notifications(self) -> None:
        """비동기 테스트 래퍼 - 다중 알림"""
        asyncio.run(self.test_sse_multiple_notifications())