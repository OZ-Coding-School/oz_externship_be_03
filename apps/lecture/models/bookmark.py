from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class LectureBookmark(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, related_name="lecture_bookmarks"
    )
    lecture = models.ForeignKey(
        "lecture.CrawledLecture", on_delete=models.CASCADE, null=False, related_name="bookmarks"
    )

    class Meta:
        db_table = "lecture_bookmarks"
        unique_together = [["user", "lecture"]]

    def __str__(self) -> str:
        return f"{self.user.nickname} - {self.lecture.title}"
