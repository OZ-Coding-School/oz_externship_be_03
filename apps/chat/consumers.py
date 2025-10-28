# apps/chat/consumers.py

import json
from typing import Any

from channels.db import database_sync_to_async  # type: ignore[import-untyped]
from channels.generic.websocket import (  # type: ignore[import-untyped]
    AsyncJsonWebsocketConsumer,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup

from .services import ChatMessageService


class ChatConsumer(AsyncJsonWebsocketConsumer):  # type: ignore[misc]
    study_group_id: int
    room_group_name: str

    async def connect(self) -> None:
        self.study_group_id = self.scope["url_route"]["kwargs"]["study_group_id"]
        self.room_group_name = f"chat_{self.study_group_id}"
        user = self.scope["user"]

        if not await self.is_valid_study_group() or not await self.is_group_member(user):
            await self.close(code=403)
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # '읽음 처리' 로직 구현
        if user.is_authenticated:
            try:
                latest_message = (
                    await ChatMessage.objects.filter(study_group_id=self.study_group_id)
                    .order_by("-created_at")
                    .afirst()
                )

                if latest_message:
                    await LastReadMessage.objects.aupdate_or_create(
                        user=user,
                        study_group_id=self.study_group_id,
                        defaults={"message": latest_message},
                    )
            except ChatMessage.DoesNotExist:
                pass

    async def disconnect(self, close_code: int) -> None:
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        message_type = content.get("type")
        user = self.scope["user"]

        if message_type == "chat.message":
            message_content = content.get("content", "").strip()  # Ensure message_content is always a string

            if user.is_authenticated:
                await self.create_chat_message(user, message_content)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message_content,
                    "sender_id": user.id if user.is_authenticated else None,
                },
            )

        elif message_type == "chat.edit_message":
            message_id = content.get("message_id")
            new_content = content.get("new_content", "").strip()

            if user.is_authenticated and message_id and new_content:
                await self.edit_chat_message(user, message_id, new_content)
    async def is_valid_study_group(self) -> bool:
        return await StudyGroup.objects.filter(id=self.study_group_id).aexists()

    async def is_group_member(self, user: AbstractBaseUser) -> bool:
        if not user.is_authenticated or not isinstance(user, get_user_model()):
            return False
        return await GroupMember.objects.filter(study_group_id=self.study_group_id, user=user).aexists()

    async def create_chat_message(self, user: AbstractBaseUser, content: str) -> None:
        """
        Asynchronously creates a chat message in the database.
        """
        study_group = await StudyGroup.objects.aget(id=self.study_group_id)
        await database_sync_to_async(ChatMessageService.create_chat_message)(
            sender=user,
            study_group=study_group,
            content=content,
        )

    async def edit_chat_message(self, user: AbstractBaseUser, message_id: int, new_content: str) -> None:
        try:
            message = await ChatMessage.objects.aget(id=message_id, study_group_id=self.study_group_id)
        except ChatMessage.DoesNotExist:
            await self.send_json({"type": "error", "code": "MESSAGE_NOT_FOUND", "message": "메시지를 찾을 수 없습니다."})
            return

        if message.sender != user:
            await self.send_json({"type": "error", "code": "NOT_MESSAGE_SENDER", "message": "메시지 발신자만 수정할 수 있습니다."})
            return

        updated_message = await database_sync_to_async(ChatMessageService.edit_chat_message)(
            message=message,
            new_content=new_content,
        )

        # Broadcast the updated message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message_edited",
                "message_id": updated_message.id,
                "editor_id": user.id,
                "new_content": updated_message.content,
                "updated_at": updated_message.updated_at.isoformat(),
            },
        )
    # Receive message from room group
    async def chat_message(self, event: dict[str, Any]) -> None:
        message = event["message"]
        sender_id = event["sender_id"]

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "chat.message", "message": message, "sender_id": sender_id},
                ensure_ascii=False,
            )
        )

    async def chat_message_edited(self, event: dict[str, Any]) -> None:
        message_id = event["message_id"]
        editor_id = event["editor_id"]
        new_content = event["new_content"]
        updated_at = event["updated_at"]

        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.message.edited",
                    "message_id": message_id,
                    "editor_id": editor_id,
                    "new_content": new_content,
                    "updated_at": updated_at,
                },
                ensure_ascii=False,
            )
        )
