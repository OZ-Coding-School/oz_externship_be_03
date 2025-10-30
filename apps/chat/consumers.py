# apps/chat/consumers.py

import json
from typing import Any, cast

from channels.db import database_sync_to_async  # type: ignore[import-untyped]
from channels.generic.websocket import (  # type: ignore[import-untyped]
    AsyncJsonWebsocketConsumer,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from rest_framework.exceptions import APIException

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User

from .exceptions import ChatMessageNotFoundException, ChatMessageNotSenderException
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

        try:
            if message_type == "chat.message":
                message_content = content.get("content", "").strip()
                message = None
                if user.is_authenticated:
                    message = await self.create_chat_message(user, message_content)

                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "message_id": message.id if message else None,
                        "message": message_content,
                        "sender_id": user.id if user.is_authenticated else None,
                    },
                )
            elif message_type == "chat.delete_message":
                message_id = content.get("message_id")

                if user.is_authenticated and message_id:
                    await self.delete_chat_message(user, message_id)
        except APIException as e:
            await self.send_json({"type": "error", "code": e.default_code, "message": e.default_detail})

    async def _get_message_and_verify_sender(self, user: User, message_id: int) -> ChatMessage:
        try:
            message = await ChatMessage.objects.aget(id=message_id, study_group_id=self.study_group_id)
        except ChatMessage.DoesNotExist:
            raise ChatMessageNotFoundException

        if message.sender != user:
            raise ChatMessageNotSenderException

        return message

    async def is_valid_study_group(self) -> bool:
        return await StudyGroup.objects.filter(id=self.study_group_id).aexists()

    async def is_group_member(self, user: AbstractBaseUser) -> bool:
        if not user.is_authenticated or not isinstance(user, get_user_model()):
            return False
        return await GroupMember.objects.filter(study_group_id=self.study_group_id, user=user).aexists()

    async def create_chat_message(self, user: User, content: str) -> ChatMessage:
        """
        Asynchronously creates a chat message in the database.
        """
        study_group = await StudyGroup.objects.aget(id=self.study_group_id)
        message = await database_sync_to_async(ChatMessageService.create_chat_message)(
            sender=user,
            study_group=study_group,
            content=content,
        )
        return cast(ChatMessage, message)

    async def delete_chat_message(self, user: User, message_id: int) -> None:
        message = await self._get_message_and_verify_sender(user, message_id)
        await database_sync_to_async(ChatMessageService.delete_chat_message)(message=message)

        # Broadcast the deleted message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message_deleted",
                "message_id": message_id,
                "deleter_id": user.id,
            },
        )

    # Receive message from room group
    async def chat_message(self, event: dict[str, Any]) -> None:
        message_id = event["message_id"]
        message = event["message"]
        sender_id = event["sender_id"]

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "chat.message", "message_id": message_id, "message": message, "sender_id": sender_id},
                ensure_ascii=False,
            )
        )

    async def chat_message_deleted(self, event: dict[str, Any]) -> None:
        message_id = event["message_id"]
        deleter_id = event["deleter_id"]

        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.message.deleted",
                    "message_id": message_id,
                    "deleter_id": deleter_id,
                },
                ensure_ascii=False,
            )
        )
