from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class RecruitmentSearchLog(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recruitment_search_logs",
    )
    keyword = models.CharField(max_length=255)

    class Meta:
        db_table = "recruitment_search_logs"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["keyword"]),
        ]
        verbose_name = "공고 검색 로그"
        verbose_name_plural = "공고 검색 로그 목록"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.keyword} ({self.created_at:%Y-%m-%d %H:%M})"
