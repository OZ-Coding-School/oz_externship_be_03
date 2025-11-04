from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

from .recruitments import Recruitment


class ApplicationStatus(models.TextChoices):
    APPROVED = "APPROVED", "승인"
    REVIEWING = "REVIEWING", "검토중"
    PENDING = "PENDING", "대기"
    REJECTED = "REJECTED", "거절"


class Application(models.Model):
    if TYPE_CHECKING:
        id: int
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="applications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")

    self_introduction = models.TextField()
    motivation = models.TextField()
    objective = models.CharField(max_length=300)
    available_time = models.CharField(max_length=200)
    has_study_experience = models.BooleanField(default=False)
    study_experience = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("recruitment", "user")  # 동일 공고 중복 지원 방지
        indexes = [
            models.Index(fields=["recruitment", "status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"application({self.id}) by user({self.user.id}) to recruitment=({self.recruitment.id})"
