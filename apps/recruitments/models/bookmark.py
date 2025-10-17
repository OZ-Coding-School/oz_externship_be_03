from django.db import models
from apps.core.models import BaseModel
from django.conf import settings
from .recruitment import Recruitment


class RecruitmentBookmark(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="bookmarks")  # 공고
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recruitment_bookmarks"
    )  # 유저

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "recruitment"], name="unique_user_bookmark")
        ]  # 중복 방지

    def __str__(self) -> str:
        username = getattr(self.user, "username", str(self.user))
        return f"{username} 북마크 {self.recruitment.title}"
