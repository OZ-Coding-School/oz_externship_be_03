import uuid

from django.db import models


class DifficultyEnum(models.TextChoices):
    EASY = "EASY", "초급"
    NORMAL = "NORMAL", "중급"
    HARD = "HARD", "어려움"


class CrawledLecture(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=255)
    instructor = models.CharField(max_length=20)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    duration = models.SmallIntegerField()
    difficulty = models.CharField(max_length=10, choices=DifficultyEnum.choices)
    description = models.TextField()
    platform = models.CharField(max_length=50)
    original_price = models.BigIntegerField(default=0)
    discount_price = models.BigIntegerField(default=0)
    url_link = models.CharField(max_length=500)
    thumbnail_img_url = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = "crawled_lectures"
        unique_together = [["platform", "title"]]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.platform}] {self.title}"
