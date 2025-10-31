from typing import Any

from rest_framework import serializers

from apps.chat.models import ChatMessage, LastReadMessage
from apps.users.models import User
from apps.users.serializers.user_profile_serializers import UserProfileSerializer


class ChatMessageSerializer(serializers.ModelSerializer[ChatMessage]):
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    sender_nickname = serializers.CharField(source="sender.nickname", read_only=True)
    study_group_id = serializers.IntegerField(source="study_group.id", read_only=True)
    file_url = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender_id",
            "sender_nickname",
            "study_group_id",
            "content",
            "file_url",
            "is_read",
            "created_at",
        ]

    def get_file_url(self, obj: ChatMessage) -> None:
        # ChatMessage 모델에 file_url 필드가 없으므로 항상 None을 반환합니다.
        # 파일 메시지 전송 기능이 추가되면 이 부분을 수정해야 합니다.
        return None

    def get_is_read(self, obj: ChatMessage) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False  # Unauthenticated users cannot have read status

        try:
            last_read_message = LastReadMessage.objects.get(user=request.user, study_group=obj.study_group)
            return obj.id <= last_read_message.message.id
        except LastReadMessage.DoesNotExist:
            return False  # No last read message for this user in this group


class LastMessageSerializer(serializers.Serializer[Any]):
    content = serializers.CharField(help_text="마지막 메시지 내용")
    sender_nickname = serializers.CharField(help_text="마지막 메시지 발신자 닉네임")
    created_at = serializers.DateTimeField(help_text="마지막 메시지 전송 일시")


class ChatRoomSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(help_text="스터디 그룹 ID")
    name = serializers.CharField(help_text="스터디 그룹명")
    last_message = LastMessageSerializer(allow_null=True, help_text="마지막 메시지 정보")
    unread_count = serializers.IntegerField(default=0, help_text="안 읽은 메시지 수")
