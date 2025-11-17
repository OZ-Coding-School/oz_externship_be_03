import json
from typing import Any, Dict, Set, cast
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import (
    AsyncJsonWebsocketConsumer,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django_redis import get_redis_connection  # type: ignore[import-untyped]

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models.user import User


class ChatConsumer(AsyncJsonWebsocketConsumer):  # type: ignore[misc]
    study_group_uuid: UUID
    room_group_name: str
    user: AbstractBaseUser
    redis_key: str

    async def connect(self) -> None:
        self.study_group_uuid = self.scope["url_route"]["kwargs"]["study_group_uuid"]
        self.room_group_name = f"chat_{self.study_group_uuid}"
        self.redis_key = f"online_users:{self.study_group_uuid}"
        self.user = self.scope["user"]

        if not await self.is_valid_study_group() or not await self.is_group_member(self.user):
            await self.close(code=403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        if self.user.is_authenticated:
            assert isinstance(self.user, User)
            await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)

        await self.accept()

        if self.user.is_authenticated:
            assert isinstance(self.user, User)
            await self.mark_messages_as_read()

            online_users = await self._add_user_and_get_online_users()

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "online_users_update",
                    "online_users": online_users,
                },
            )

    async def disconnect(self, close_code: int) -> None:
        if self.user.is_authenticated:
            assert isinstance(self.user, User)
            online_users = await self._remove_user_and_get_online_users()

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "online_users_update",
                    "online_users": online_users,
                },
            )

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        if self.user.is_authenticated:
            assert isinstance(self.user, User)
            await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        message_type = content.get("type")
        user = cast(User, self.scope["user"])

        if message_type == "chat.message" and user.is_authenticated:
            message_content = content.get("content", "").strip()
            if not message_content:
                return

            try:
                new_message = await self.create_chat_message(user, message_content)

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "id": str(new_message.id),
                        "content": new_message.content,
                        "created_at": new_message.created_at.isoformat(),
                        "sender": {
                            "id": str(user.id),
                            "nickname": user.nickname,
                        },
                    },
                )
            except Exception:
                await self.send_json({"type": "error", "message": "Failed to send message"})

    async def is_valid_study_group(self) -> bool:
        try:
            return await StudyGroup.objects.filter(uuid=self.study_group_uuid).aexists()
        except Exception:
            return False

    async def is_group_member(self, user: AbstractBaseUser) -> bool:
        if not user.is_authenticated or not isinstance(user, get_user_model()):
            return False
        try:
            return await GroupMember.objects.filter(study_group__uuid=self.study_group_uuid, user=user).aexists()
        except Exception:
            return False

    async def create_chat_message(self, user: AbstractBaseUser, content: str) -> ChatMessage:
        study_group = await StudyGroup.objects.aget(uuid=self.study_group_uuid)
        return await ChatMessage.objects.acreate(
            sender=cast(User, user),
            study_group=study_group,
            content=content,
        )

    async def chat_message(self, event: Dict[str, Any]) -> None:
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.message",
                    "id": event["id"],
                    "content": event["content"],
                    "created_at": event["created_at"],
                    "sender": event["sender"],
                },
                ensure_ascii=False,
            )
        )

    async def system_message(self, event: Dict[str, Any]) -> None:
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.system",
                    "message": event["message"],
                },
                ensure_ascii=False,
            )
        )

    async def force_disconnect(self, event: Dict[str, Any]) -> None:
        disconnected_study_group_id = event.get("study_group_id")
        if disconnected_study_group_id == self.study_group_uuid:
            await self.close(code=4001)

    async def mark_messages_as_read(self) -> None:
        try:
            study_group = await StudyGroup.objects.aget(uuid=self.study_group_uuid)

            latest_message = await ChatMessage.objects.filter(study_group_id=study_group.id).alast()

            if latest_message:
                await LastReadMessage.objects.aupdate_or_create(
                    study_group=study_group,
                    user=self.user,
                    defaults={"message": latest_message},
                )
        except Exception:
            pass

    @database_sync_to_async  # type: ignore[misc]
    def _add_user_and_get_online_users(self) -> list[dict[str, str]]:
        user = cast(User, self.user)
        try:
            redis_client = get_redis_connection("default")

            redis_client.sadd(self.redis_key, str(user.id))
            redis_client.expire(self.redis_key, 3600)  # 1 hour TTL

            online_user_ids = redis_client.smembers(self.redis_key)
            user_ids = [uid.decode("utf-8") if isinstance(uid, bytes) else uid for uid in online_user_ids]

            if not user_ids:
                return []

            users = User.objects.filter(id__in=user_ids).values("id", "nickname", "name")

            return [
                {
                    "id": str(user["id"]),
                    "nickname": user["nickname"],
                    "name": user["name"],
                }
                for user in users
            ]
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in _add_user_and_get_online_users: {e}")
            return []

    @database_sync_to_async  # type: ignore[misc]
    def _remove_user_and_get_online_users(self) -> list[dict[str, str]]:
        user = cast(User, self.user)
        try:
            redis_client = get_redis_connection("default")

            redis_client.srem(self.redis_key, str(user.id))

            online_user_ids = redis_client.smembers(self.redis_key)
            user_ids = [uid.decode("utf-8") if isinstance(uid, bytes) else uid for uid in online_user_ids]

            if not user_ids:
                return []

            users = User.objects.filter(id__in=user_ids).values("id", "nickname", "name")

            return [
                {
                    "id": str(user["id"]),
                    "nickname": user["nickname"],
                    "name": user["name"],
                }
                for user in users
            ]
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in _remove_user_and_get_online_users: {e}")
            return []

    async def online_users_update(self, event: Dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": "online.users",
                "count": len(event["online_users"]),
                "users": event["online_users"],
            }
        )
