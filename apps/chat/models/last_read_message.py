from django.db import models

from apps.core.models import TimeStampModel


class LastReadMessage(TimeStampModel):
    study_group = models.ForeignKey(
        "studies.StudyGroup",
        on_delete=models.CASCADE,
        related_name="last_read_messages",
        verbose_name="스터디 그룹",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="last_read_messages",
        verbose_name="유저",
    )
    message = models.ForeignKey(
        "chat.ChatMessage",
        on_delete=models.CASCADE,
        related_name="read_by_users",
        verbose_name="마지막으로 읽은 메시지",
    )

    class Meta:
        db_table = "last_read_messages"
        # 한 유저는 그룹당 하나의 마지막 읽은 메시지만 가짐
        unique_together = ("study_group", "user")
        verbose_name = "마지막으로 읽은 메시지"
        verbose_name_plural = "마지막으로 읽은 메시지 목록"

    def __str__(self) -> str:
        return f"{self.user} last read {self.message.id} in {self.study_group}"
