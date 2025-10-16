from django.conf import settings
from django.db import models


class Review(models.Model):
    id = models.BigAutoField(primary_key=True)
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
    star_rating = models.PositiveSmallIntegerField()
    content = models.CharField(max_length=300)
    is_public = models.BooleanField(default=False)  # 운영 및 신고 대응을 위해
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reviews"
        # 테이블 제약
        constraints = [
            models.UniqueConstraint(
                fields=["user", "study_group"],
                name="uq_reviews_user_group",
            ),
            models.CheckConstraint(
                check=models.Q(star_rating__gte=1, star_rating__lte=5),
                name="ck_reviews+star_rating_1_5",
            ),
        ]
        indexes = [
            models.Index(fields=["study_group", "-created_at"], name="ix_reviews_group_created_desc"),
            models.Index(fields=["user", "-created_at"], name="ix_reviews_user_created_desc"),
            models.Index(fields=["is_public"], name="ix_reviews_public"),
        ]

    def __str__(self):
        return f"Review <{self.id}> user={self.user_id}, group={self.study_group_id}, rate={self.star_rating}"
