from datetime import timezone
from typing import Any, Optional

from django.utils import timezone as tz
from rest_framework import serializers

from apps.chat.models import ChatMessage, LastReadMessage
from apps.users.models import User
from apps.users.serializers.user_profile_serializers import UserProfileSerializer


class ChatMessageSerializer(serializers.ModelSerializer[ChatMessage]):
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    sender_nickname = serializers.CharField(source="sender.nickname", read_only=True)
    study_group_id = serializers.IntegerField(source="study_group.id", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender_id",
            "sender_nickname",
            "study_group_id",
            "content",
            "is_read",
            "created_at",
        ]

    def get_is_read(self, obj: ChatMessage) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False  # Unauthenticated users cannot have read status

        try:
            last_read_message = LastReadMessage.objects.get(user=request.user, study_group=obj.study_group)
            return obj.id <= last_read_message.message_id
        except LastReadMessage.DoesNotExist:
            return False  # No last read message for this user in this group


class LastMessageSerializer(serializers.Serializer[Any]):
    content = serializers.CharField(help_text="마지막 메시지 내용", source="last_message_content")
    sender_nickname = serializers.CharField(
        help_text="마지막 메시지 발신자 닉네임", source="last_message_sender_nickname"
    )
    created_at = serializers.DateTimeField(
        help_text="마지막 메시지 전송 일시", source="last_message_created_at", format="%Y-%m-%dT%H:%M:%SZ"
    )


class ChatRoomSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(help_text="스터디 그룹 ID")
    name = serializers.CharField(help_text="스터디 그룹명")
    last_message = serializers.SerializerMethodField(help_text="마지막 메시지 정보")
    unread_count = serializers.IntegerField(default=0, help_text="안 읽은 메시지 수")

    def get_last_message(self, obj: Any) -> Optional[dict[str, Any]]:
        if obj["last_message_content"] is None:
            return None

        created_at_str = None
        if obj["last_message_created_at"]:
            dt = obj["last_message_created_at"]
            # Ensure datetime is timezone-aware and convert to ISO 8601 with 'Z'
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                # Assume UTC if timezone-naive, or if offset is not available
                dt = tz.make_aware(dt, timezone.utc)
            else:
                # Convert to UTC if already timezone-aware with an offset
                dt = tz.localtime(dt, timezone.utc)
            created_at_str = dt.isoformat().replace("+00:00", "Z")

        return {
            "content": obj["last_message_content"],
            "sender_nickname": obj["last_message_sender_nickname"],
            "created_at": created_at_str,
        }
