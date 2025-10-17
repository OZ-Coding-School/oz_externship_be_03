from django.db import models

from apps.core.models import BaseModel


class RatingEnum(models.TextChoices):
    FIVE = "5_OUT_OF_5_STARS", "5점"
    FOUR = "4_OUT_OF_5_STARS", "4점"
    THREE = "3_OUT_OF_5_STARS", "3점"
    TWO = "2_OUT_OF_5_STARS", "2점"
    ONE = "1_OUT_OF_5_STARS", "1점"


class CrawledLectureReview(BaseModel):
    lecture = models.ForeignKey("lecture.CrawledLecture", on_delete=models.CASCADE, null=False, related_name="reviews")
    rating = models.CharField(max_length=20, choices=RatingEnum.choices, null=False)
    content = models.TextField(null=False)

    class Meta:
        db_table = "crawled_lecture_reviews"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.lecture.title} - {self.rating}"
