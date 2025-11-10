# apps/chat/consumers.py

import json
from typing import Any, cast

from channels.db import database_sync_to_async
from channels.generic.websocket import (
    AsyncJsonWebsocketConsumer,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models.user import User


class ChatConsumer(AsyncJsonWebsocketConsumer):  # type: ignore[misc]
    study_group_id: int
    room_group_name: str
    user: AbstractBaseUser

    async def connect(self) -> None:
        self.study_group_id = self.scope["url_route"]["kwargs"]["study_group_id"]
        self.room_group_name = f"chat_{self.study_group_id}"
        self.user = self.scope["user"]

        if not await self.is_valid_study_group() or not await self.is_group_member(self.user):
            await self.close(code=403)
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Join user-specific group to allow direct messaging
        if self.user.is_authenticated:
            assert isinstance(self.user, User)
            await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)

        await self.accept()

        # Mark all messages as read upon connection
        if self.user.is_authenticated:
            assert isinstance(self.user, User)
            await self.mark_messages_as_read()

    async def mark_messages_as_read(self) -> None:
        """
        Marks all messages in the current study group as read for the current user.
        """
        latest_message = await ChatMessage.objects.filter(study_group_id=self.study_group_id).alast()
        if latest_message:
            await LastReadMessage.objects.aupdate_or_create(
                study_group_id=self.study_group_id,
                user=self.user,
                defaults={"message": latest_message},
            )

    async def disconnect(self, close_code: int) -> None:
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Leave user-specific group
        if self.user.is_authenticated:
            assert isinstance(self.user, User)
            await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)

    # Receive message from WebSocket
    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        message_type = content.get("type")
        user = self.scope["user"]

        if message_type == "chat.message":
            message_content = content.get("content", "").strip()  # Ensure message_content is always a string

            sender_id = None
            if user.is_authenticated:
                assert isinstance(user, User)
                await self.create_chat_message(user, message_content)
                sender_id = user.id

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message_content,
                    "sender_id": sender_id,
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

    async def system_message(self, event: dict[str, Any]) -> None:
        """Handler for system messages."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.system",
                    "message": event["message"],
                },
                ensure_ascii=False,
            )
        )

    async def force_disconnect(self, event: dict[str, Any]) -> None:
        """
        Handler for the 'force_disconnect' event.
        Closes the WebSocket connection.
        """
        disconnected_study_group_id = event.get("study_group_id")
        if disconnected_study_group_id == self.study_group_id:
            await self.close(code=4001)
