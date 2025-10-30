import json
import logging
from typing import Any, AsyncGenerator, Dict, Generator, List

import redis.asyncio as redis
from django.conf import settings

logger = logging.getLogger(__name__)


class RedisPubSubService:
    def __init__(self) -> None:
        self.redis_client = redis.Redis.from_url(getattr(settings, "CACHES", {}).get("default", {}).get("LOCATION"))

    def get_user_channel(self, user_id: int) -> str:
        """사용자별 알림 채널명 생성"""
        return f"notifications:user_{user_id}"

    def get_group_channel(self, group_id: int) -> str:
        """그룹별 알림 채널명 생성"""
        return f"notifications:group_{group_id}"

    async def publish_notification(self, user_id: int, notification_data: Dict[str, Any]) -> None:
        """특정 사용자 채널에 알림 발행"""
        channel = self.get_user_channel(user_id)
        message = json.dumps(notification_data, ensure_ascii=False, default=str)

        try:
            await self.redis_client.publish(channel, message)
            logger.info(f"채널{channel}에 게시된 알림:{message}")
        except Exception as e:
            logger.error(f"{channel}에 알림을 게시하지 못했습니다.{e}")

    async def publish_group_notification(self, group_id: int, notification_data: Dict[str, Any]) -> None:
        """특정 그룹 채널에 알림 발행"""
        channel = self.get_user_channel(group_id)
        message = json.dumps(notification_data, ensure_ascii=False, default=str)

        try:
            await self.redis_client.publish(channel, message)
            logger.info(f"그룹 채널{channel}에 게시된 알림:{message}")
        except Exception as e:
            logger.error(f"그룹 {channel}에 알림을 게시하지 못했습니다.{e}")

    async def subscribe_notification(self, user_id: int,group_ids: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """사용자 알림 채널 구독 및 메시지 스트리밍"""
        personal_channel = self.get_user_channel(user_id)
        group_channel = [self.get_group_channel(group_id) for group_id in group_ids]
        all_channels = group_channel + [personal_channel]
        pubsub = self.redis_client.pubsub()

        try:
            await pubsub.subscribe(all_channels)
            logger.info(f"채널 구독:{all_channels}")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        notification_data = json.loads(message["data"])
                        yield notification_data
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.error(f"{all_channels}에서 메시지를 디코딩하지 못했습니다:{e}")

        except Exception as e:
            logger.error(f"구독 실패:{e}")
        finally:
            await pubsub.close()


notification_pubsub: RedisPubSubService = RedisPubSubService()
