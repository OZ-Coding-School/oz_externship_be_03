from django.db import models

from apps.core.models import BaseModel


class Tag(BaseModel):
    name = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = "tags"
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self) -> str:
        return self.name
