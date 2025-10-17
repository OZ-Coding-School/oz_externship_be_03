from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Category(BaseModel):
    name = models.CharField(max_length=255, unique=True, null=False)

    class Meta:
        db_table = "categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LectureCategory(BaseModel):
    pk = models.CompositePrimaryKey("lecture_id", "category_id")
    lecture = models.ForeignKey(
        "lecture.CrawledLecture", on_delete=models.CASCADE, null=False, related_name="lecture_categories"
    )
    category = models.ForeignKey("Category", on_delete=models.CASCADE, null=False, related_name="lecture_categories")

    class Meta:
        db_table = "lecture_categories"

    def __str__(self) -> str:
        return f"{self.lecture.title} - {self.category.name}"


class UserPreferCategory(BaseModel):
    pk = models.CompositePrimaryKey("user_id", "category_id")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, related_name="prefer_categories"
    )
    category = models.ForeignKey("Category", on_delete=models.CASCADE, null=False, related_name="preferred_by_users")

    class Meta:
        db_table = "user_prefer_categories"

    def __str__(self) -> str:
        return f"{self.user.nickname} - {self.category.name}"  # type:ignore # TODO:user파트 머지 후 주석삭제
