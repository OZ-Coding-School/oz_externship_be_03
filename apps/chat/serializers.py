from typing import Any

from rest_framework import serializers

from apps.chat.models import ChatMessage
from apps.users.serializers.user_profile_serializers import UserProfileSerializer


class ChatMessageSerializer(serializers.ModelSerializer[ChatMessage]):
    sender = UserProfileSerializer(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ("id", "sender", "content", "created_at")


class ChatRoomSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(help_text="스터디 그룹 ID")
    name = serializers.CharField(help_text="스터디 그룹명")
    last_message = serializers.CharField(allow_null=True, help_text="마지막 메시지 내용")
    unread_count = serializers.IntegerField(default=0, help_text="안 읽은 메시지 수")
