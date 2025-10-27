import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, patch

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.notifications.services.redis_pubsub_classify import RedisPubSubService


class RedisPubSubServiceTest(IsolatedRedisTestClient):
    def setUp(self) -> None:
        super().setUp()
        # 테스트 중 로깅 비활성화
        logging.disable(logging.CRITICAL)
        self.pubsub_service = RedisPubSubService()
        self.test_user_id = 123
        self.test_notification_data = {
            "id": 1,
            "type": "APPLICATION_CREATED",
            "content": "새로운 지원자가 지원했습니다.",
            "created_at": "2024-01-01T10:00:00Z",
            "is_read": False,
        }

    async def test_get_user_channel(self) -> None:
        """사용자 채널명 생성 테스트"""
        user_id = 123
        expected_channel = "notifications:user_123"

        channel = self.pubsub_service.get_user_channel(user_id)

        self.assertEqual(channel, expected_channel)

    async def test_publish_notification_success(self) -> None:
        """알림 발행 성공 테스트"""
        with patch.object(self.pubsub_service.redis_client, "publish", new_callable=AsyncMock) as mock_publish:
            mock_publish.return_value = 1  # Redis publish는 구독자 수를 반환

            await self.pubsub_service.publish_notification(
                user_id=self.test_user_id, notification_data=self.test_notification_data
            )

            # publish가 올바른 채널과 메시지로 호출되었는지 확인
            expected_channel = "notifications:user_123"
            expected_message = json.dumps(self.test_notification_data, ensure_ascii=False, default=str)
            mock_publish.assert_called_once_with(expected_channel, expected_message)

    async def test_publish_notification_redis_error(self) -> None:
        """Redis 발행 오류 처리 테스트"""
        with patch.object(self.pubsub_service.redis_client, "publish", new_callable=AsyncMock) as mock_publish:
            mock_publish.side_effect = Exception("Redis connection error")

            # 예외가 발생해도 함수가 정상적으로 완료되어야 함 (로깅만 하고 재발생시키지 않음)
            await self.pubsub_service.publish_notification(
                user_id=self.test_user_id, notification_data=self.test_notification_data
            )

            mock_publish.assert_called_once()

    async def test_subscribe_user_notification_success(self) -> None:
        """사용자 알림 구독 성공 테스트"""
        # Mock pubsub 객체 생성
        mock_pubsub = AsyncMock()
        mock_messages: list[Dict[str, Any]] = [
            {"type": "subscribe", "channel": "notifications:user_123", "data": 1},
            {"type": "message", "channel": "notifications:user_123", "data": json.dumps(self.test_notification_data)},
            {
                "type": "message",
                "channel": "notifications:user_123",
                "data": json.dumps({"id": 2, "content": "두 번째 알림"}),
            },
        ]

        async def async_messages() -> AsyncGenerator[Dict[str, Any], None]:
            for message in mock_messages:
                yield message

        # listen()을 실제 async generator로 설정
        mock_pubsub.listen = async_messages

        with patch.object(self.pubsub_service.redis_client, "pubsub", return_value=mock_pubsub):
            notifications = []
            async for notification in self.pubsub_service.subscribe_user_notification(self.test_user_id):
                notifications.append(notification)
                if len(notifications) >= 2:  # 2개 메시지만 수집하고 종료
                    break

            # 구독 및 메시지 수신 확인
            mock_pubsub.subscribe.assert_called_once_with("notifications:user_123")
            self.assertEqual(len(notifications), 2)
            self.assertEqual(notifications[0], self.test_notification_data)
            self.assertEqual(notifications[1]["id"], 2)

    async def test_subscribe_user_notification_json_decode_error(self) -> None:
        """JSON 디코딩 오류 처리 테스트"""
        mock_pubsub = AsyncMock()
        mock_messages: list[Dict[str, Any]] = [
            {"type": "subscribe", "channel": "notifications:user_123", "data": 1},
            {"type": "message", "channel": "notifications:user_123", "data": "invalid json"},
            {"type": "message", "channel": "notifications:user_123", "data": json.dumps(self.test_notification_data)},
        ]

        async def async_messages() -> AsyncGenerator[Dict[str, Any], None]:
            for message in mock_messages:
                yield message

        # listen()을 실제 async generator로 설정
        mock_pubsub.listen = async_messages

        with patch.object(self.pubsub_service.redis_client, "pubsub", return_value=mock_pubsub):
            notifications = []
            async for notification in self.pubsub_service.subscribe_user_notification(self.test_user_id):
                notifications.append(notification)
                if len(notifications) >= 1:  # 유효한 메시지 1개만 수집
                    break

            # 유효한 메시지만 수신되어야 함 (invalid json은 무시)
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0], self.test_notification_data)

    async def test_subscribe_user_notification_connection_error(self) -> None:
        """Redis 연결 오류 처리 테스트"""
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe.side_effect = Exception("Redis connection error")

        with patch.object(self.pubsub_service.redis_client, "pubsub", return_value=mock_pubsub):
            notifications = []
            async for notification in self.pubsub_service.subscribe_user_notification(self.test_user_id):
                notifications.append(notification)

            # 연결 오류 시 아무 메시지도 수신되지 않아야 함
            self.assertEqual(len(notifications), 0)
            # pubsub.close()가 호출되었는지 확인
            mock_pubsub.close.assert_called_once()

    async def test_json_serialization_with_special_characters(self) -> None:
        """특수 문자가 포함된 JSON 직렬화 테스트"""
        special_data = {"id": 1, "content": "한글 메시지 테스트! 🎉", "emoji": "😀🎊", "special_chars": "!@#$%^&*()"}

        with patch.object(self.pubsub_service.redis_client, "publish", new_callable=AsyncMock) as mock_publish:
            await self.pubsub_service.publish_notification(user_id=self.test_user_id, notification_data=special_data)

            # ensure_ascii=False로 한글과 이모지가 올바르게 직렬화되는지 확인
            expected_message = json.dumps(special_data, ensure_ascii=False, default=str)
            mock_publish.assert_called_once_with("notifications:user_123", expected_message)

            # 직렬화된 메시지에 한글과 이모지가 포함되어 있는지 확인
            serialized_message = mock_publish.call_args[0][1]
            self.assertIn("한글 메시지 테스트!", serialized_message)
            self.assertIn("😀🎊", serialized_message)

    async def test_multiple_users_different_channels(self) -> None:
        """여러 사용자가 각각 다른 채널을 사용하는지 테스트"""
        user_ids = [123, 456, 789]
        expected_channels = ["notifications:user_123", "notifications:user_456", "notifications:user_789"]

        for i, user_id in enumerate(user_ids):
            channel = self.pubsub_service.get_user_channel(user_id)
            self.assertEqual(channel, expected_channels[i])

        # 모든 채널이 서로 다른지 확인
        channels = [self.pubsub_service.get_user_channel(uid) for uid in user_ids]
        self.assertEqual(len(set(channels)), len(user_ids))

    # 동기 테스트 래퍼들
    def test_async_get_user_channel(self) -> None:
        """비동기 테스트 래퍼 - 채널명 생성"""
        asyncio.run(self.test_get_user_channel())

    def test_async_publish_notification_success(self) -> None:
        """비동기 테스트 래퍼 - 알림 발행 성공"""
        asyncio.run(self.test_publish_notification_success())

    def test_async_publish_notification_redis_error(self) -> None:
        """비동기 테스트 래퍼 - Redis 발행 오류"""
        asyncio.run(self.test_publish_notification_redis_error())

    def test_async_subscribe_user_notification_success(self) -> None:
        """비동기 테스트 래퍼 - 구독 성공"""
        asyncio.run(self.test_subscribe_user_notification_success())

    def test_async_subscribe_user_notification_json_decode_error(self) -> None:
        """비동기 테스트 래퍼 - JSON 디코딩 오류"""
        asyncio.run(self.test_subscribe_user_notification_json_decode_error())

    def test_async_subscribe_user_notification_connection_error(self) -> None:
        """비동기 테스트 래퍼 - 연결 오류"""
        asyncio.run(self.test_subscribe_user_notification_connection_error())

    def test_async_json_serialization_with_special_characters(self) -> None:
        """비동기 테스트 래퍼 - 특수 문자 직렬화"""
        asyncio.run(self.test_json_serialization_with_special_characters())

    def test_async_multiple_users_different_channels(self) -> None:
        """비동기 테스트 래퍼 - 다중 사용자 채널"""
        asyncio.run(self.test_multiple_users_different_channels())
