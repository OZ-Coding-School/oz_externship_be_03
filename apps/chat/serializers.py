from typing import Any, Optional

from rest_framework import serializers

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models import StudyGroup
from apps.users.models import User


class ChatMessageSenderSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "nickname"]
        read_only_fields = fields


class ChatMessageSerializer(serializers.ModelSerializer[ChatMessage]):
    study_group_uuid = serializers.UUIDField(source="study_group.uuid")
    sender = ChatMessageSenderSerializer()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "study_group_uuid",
            "sender",
            "content",
            "created_at",
        ]
        read_only_fields = fields


class ChatRoomSerializer(serializers.ModelSerializer[StudyGroup]):
    last_message = serializers.SerializerMethodField()
    unread_message_count = serializers.IntegerField()

    class Meta:
        model = StudyGroup
        fields = ["uuid", "name", "last_message", "unread_message_count"]
        read_only_fields = fields

    def get_last_message(self, obj: Any) -> Optional[dict[str, Any]]:
        obj_last_message_is_none = (
            obj.last_message_created_at is None
            and obj.last_message_id is None
            and obj.last_message_content is None
            and obj.last_message_sender_nickname is None
        )

        if obj_last_message_is_none:
            return None

        last_message_created_at = obj.last_message_created_at
        return {
            "id": obj.last_message_id,
            "content": obj.last_message_content,
            "sender_nickname": obj.last_message_sender_nickname,
            "created_at": last_message_created_at.strftime("%Y-%m-%d %H:%M:%S") if last_message_created_at else None,
        }
