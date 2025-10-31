# apps/chat/consumers.py

import json
from typing import Any, cast

from channels.db import database_sync_to_async
from channels.generic.websocket import (
    AsyncJsonWebsocketConsumer,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from apps.chat.models import ChatMessage
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models.user import User


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
        await ChatMessage.objects.acreate(
            sender=cast(User, user),
            study_group=study_group,
            content=content,
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
