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
    content = models.TextField(verbose_name="메시지 내용")
    file_url = models.URLField(max_length=255, null=True, blank=True, verbose_name="첨부 파일 URL")

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]
        verbose_name = "채팅 메시지"
        verbose_name_plural = "채팅 메시지 목록"

    def __str__(self) -> str:
        sender_name = getattr(self.sender, "nickname", "알 수 없는 사용자")
        return f"{self.study_group} | {sender_name}: {self.content[:20]}"
