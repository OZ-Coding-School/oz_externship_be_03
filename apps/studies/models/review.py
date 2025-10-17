from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.lecture.models.review import RatingEnum

# ── mypy 전용: 런타임 영향 X, 정적 타입체커에만 보이는 선언 ──
if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as User

    from apps.studies.models.groups import StudyGroup

    # PK가 int인 경우:
    id: int
    user: "User"
    user_id: int
    study_group: "StudyGroup"
    study_group_id: int


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
        uid = self.user.id
        gid = self.study_group.id
        return f"Review <{self.pk}> user={uid}, group={gid}, rate={self.star_rating}"
