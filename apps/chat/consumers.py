# apps/chat/consumers.py

import json
from typing import Any

from channels.db import database_sync_to_async  # type: ignore[import-untyped]
from channels.generic.websocket import (  # type: ignore[import-untyped]
    AsyncWebsocketConsumer,
)
from django.contrib.auth.models import AbstractBaseUser

from apps.studies.models.groups import StudyGroup

from .services import ChatMessageService


class ChatConsumer(AsyncWebsocketConsumer):  # type: ignore[misc]
    study_group_id: int
    room_group_name: str

    async def connect(self) -> None:
        self.study_group_id = self.scope["url_route"]["kwargs"]["study_group_id"]
        self.room_group_name = f"chat_{self.study_group_id}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        if not text_data:
            return

        text_data_json = json.loads(text_data)
        message_type = text_data_json.get("type")
        user = self.scope["user"]

        if message_type == "chat.message":
            message_content = text_data_json.get("content")

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

        # TODO: Add handlers for other event types like message.read, file.send

    @database_sync_to_async  # type: ignore[misc]
    def create_chat_message(self, user: AbstractBaseUser, content: str) -> None:
        """
        Asynchronously creates a chat message in the database.
        """
        study_group = StudyGroup.objects.get(id=self.study_group_id)
        ChatMessageService.create_chat_message(
            sender=user,  # type: ignore[arg-type]
            study_group=study_group,
            content=content,
        )

    # Receive message from room group
    async def chat_message(self, event: dict[str, Any]) -> None:
        message = event["message"]
        sender_id = event["sender_id"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"type": "chat.message", "message": message, "sender_id": sender_id}))
