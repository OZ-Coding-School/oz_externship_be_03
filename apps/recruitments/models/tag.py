from django.db import models

from apps.core.models import BaseModel


class Tag(BaseModel):
    name = models.CharField(max_length=20, unique=True)  # 태그명

    def __str__(self) -> str:
        return self.name
