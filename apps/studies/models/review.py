from typing import cast

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.lecture.models.review import RatingEnum


class Review(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    study_group = models.ForeignKey(
        "studies.StudyGroup",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    star_rating = models.CharField(
        max_length=20,
        choices=RatingEnum.choices,
        default=RatingEnum.FIVE,
        null=False,
    )
    content = models.CharField(max_length=300)

    class Meta:
        db_table = "reviews"
        # 테이블 제약
        constraints = [
            models.UniqueConstraint(
                fields=["user", "study_group"],
                name="uq_reviews_user_group",
            ),
        ]
        indexes = [
            models.Index(fields=["study_group", "-created_at"], name="ix_reviews_group_created_desc"),
            models.Index(fields=["user", "-created_at"], name="ix_reviews_user_created_desc"),
        ]

    def __str__(self) -> str:
        rid = self.pk
        uid = self.user_id
        gid = self.study_group_id
        return f"Review <{rid}> user={uid}, group={gid}, rate={self.star_rating}"
