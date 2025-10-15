import uuid

from django.db import models

from apps.core.models import UUIDBaseModel


class DifficultyEnum(models.TextChoices):
    EASY = "EASY", "초급"
    NORMAL = "NORMAL", "중급"
    HARD = "HARD", "어려움"


class PlatformEnum(models.TextChoices):
    UDEMY = "UDEMY", "Udemy"
    INFLEARN = "INFLEARN", "Inflearn"


class CrawledLecture(UUIDBaseModel):
    title = models.CharField(max_length=255, null=False)
    instructor = models.CharField(max_length=20, null=False)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, null=False)
    duration = models.SmallIntegerField(null=False)
    difficulty = models.CharField(max_length=10, choices=DifficultyEnum.choices, null=False)
    description = models.TextField(null=False)
    platform = models.CharField(max_length=10, choices=PlatformEnum.choices, null=False)
    original_price = models.BigIntegerField(default=0, null=False)
    discount_price = models.BigIntegerField(default=0, null=False)
    url_link = models.CharField(max_length=500, null=False)
    thumbnail_img_url = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "crawled_lectures"
        unique_together = [["platform", "title"]]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.platform}] {self.title}"
