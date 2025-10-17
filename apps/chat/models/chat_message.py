from django.db import models

from apps.core.models import TimeStampModel


class ChatMessage(TimeStampModel):
    sender = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_chat_messages",
        verbose_name="발신자",
    )
    study_group = models.ForeignKey(
        "studies.StudyGroup",
        on_delete=models.CASCADE,
        related_name="chat_messages",
        verbose_name="스터디 그룹",
    )
    content = models.CharField(max_length=255, verbose_name="메시지 내용")  # ERD의 varchar 타입과 일관성을 맞추기 위해 CharField로 수정

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]
        verbose_name = "채팅 메시지"
        verbose_name_plural = "채팅 메시지 목록"

    def __str__(self) -> str:
        sender_name = getattr(self.sender, "nickname", "알 수 없는 사용자")
        return f"{self.study_group} | {sender_name}: {self.content[:20]}"
