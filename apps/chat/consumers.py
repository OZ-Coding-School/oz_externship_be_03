# apps/chat/consumers.py

import json
from typing import Any

from channels.db import database_sync_to_async  # type: ignore[import-untyped]
from channels.generic.websocket import (  # type: ignore[import-untyped]
    AsyncWebsocketConsumer,
)

from apps.studies.models.groups import GroupMember, StudyGroup

# 타입 가드 및 명시적 타입 힌트를 위해 User 모델을 가져옴
from apps.users.models import User

from .services import ChatMessageService


class ChatConsumer(AsyncWebsocketConsumer):  # type: ignore[misc]
    study_group_id: int
    room_group_name: str
    user: User | Any  # scope에서 오는 user는 인증 여부에 따라 타입이 달라짐

    async def connect(self) -> None:
        self.study_group_id = self.scope["url_route"]["kwargs"]["study_group_id"]
        self.user = self.scope["user"]

        # 접속 요청 유저가 실제 그룹 멤버인지 확인 (권한 체크)
        if isinstance(self.user, User) and await self.is_user_in_group(self.user, self.study_group_id):
            self.room_group_name = f"chat_{self.study_group_id}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        else:
            # 인증되지 않았거나 그룹 멤버가 아니면 연결 거부
            await self.close()

    @database_sync_to_async  # type: ignore[misc]
    def is_user_in_group(self, user: User, study_group_id: int) -> bool:
        """DB에 접속해서 사용자가 그룹 멤버인지 확인"""
        return GroupMember.objects.filter(study_group_id=study_group_id, user=user).exists()

    async def disconnect(self, close_code: int) -> None:
        # 정상적으로 연결된 경우에만 그룹에서 나감
        if hasattr(self, "room_group_name") and self.room_group_name:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        if not text_data:
            return

        text_data_json = json.loads(text_data)
        message_type = text_data_json.get("type")

        if message_type == "chat.message":
            user = self.scope["user"]
            sender_id = None
            message_content = text_data_json.get("content")

            # user가 실제 User 모델의 인스턴스인지 확인 (타입 가드)
            if isinstance(user, User):
                # 이 블록 안에서 mypy는 user를 User 타입으로 인지하여 user.id 접근을 허용함
                sender_id = user.id
                # DB 저장 로직 실행
                await self.create_chat_message(user, message_content)

            # 채널 그룹에 메시지 방송
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message_content,
                    "sender_id": sender_id,
                },
            )

    @database_sync_to_async  # type: ignore[misc]
    def create_chat_message(self, user: User, content: str) -> None:
        """비동기 환경에서 채팅 메시지를 동기적으로 생성"""
        study_group = StudyGroup.objects.get(id=self.study_group_id)
        ChatMessageService.create_chat_message(
            sender=user,
            study_group=study_group,
            content=content,
        )

    async def chat_message(self, event: dict[str, Any]) -> None:
        message = event["message"]
        sender_id = event["sender_id"]

        await self.send(text_data=json.dumps({"type": "chat.message", "message": message, "sender_id": sender_id}))
