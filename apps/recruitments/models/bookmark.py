from django.conf import settings
from django.db import models

from .recruitments import Recruitment


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "recruitment")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["recruitment", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"recruitment: {self.recruitment.id} bookmarked by user: {self.user.email}"
