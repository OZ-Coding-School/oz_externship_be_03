
import json
import logging

from typing import Any,Dict,Generator

import redis.asyncio as redis
from django.conf import settings

logger = logging.getLogger(__name__)

class RedisPubSubService:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            getattr(settings,'CACHES',{}).get('default',{}).get('LOCATION')
        )
        self.pubsub= self.redis_client.pubsub()

    def get_user_channel(self,user_id:int)->str:
        """사용자별 알림 채널명 생성"""
        return f"notifications:user_{user_id}"

    def publish_notification(self,user_id:int,notification_data:Dict[str,Any]) -> None:
        """특정 사용자 채널에 알림 발행"""
        channel = self.get_user_channel(user_id)
        message = json.dumps(notification_data,ensure_ascii=False)

        try :
            self.redis_client.publish(channel,message)
            logger.info(f"채널{channel}에 게시된 알림:{message}")
        except Exception as e:
            logger.error(f"{channel}에 알림을 게시하지 못했습니다.{e}")

    def subscribe_user_notification(self,user_id:int)->Generator[Dict[str,Any],None,None]:
        """사용자 알림 채널 구독 및 메시지 스트리밍"""
        channel = self.get_user_channel(user_id)

        try:
            self.pubsub.subscribe(channel)
            logger.info(f"채널 구독:{channel}")

            for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        notification_data = json.loads(message["data"].decode("utf-8"))
                        yield notification_data
                    except(json.decoder.JSONDecodeError,UnicodeDecodeError)as e:
                        logger.error(f"{channel}에서 메시지를 디코딩하지 못했습니다:{e}")

        except Exception as e:
            logger.info(f"구독 실패:{e}")

    def close(self)->None:
        """연결 종료"""
        try:
            self.pubsub.close()
        except Exception as e:
            logger.error(f"연결 해제중 오류 발생:{e}")




