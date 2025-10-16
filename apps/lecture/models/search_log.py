from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class LectureSearchLog(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, related_name="lecture_search_logs"
    )
    keyword = models.CharField(max_length=255, null=False)

    class Meta:
        db_table = "lecture_search_logs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.nickname} - {self.keyword}"  # type:ignore # TODO:user파트 머지 후 주석삭제
