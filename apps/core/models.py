import uuid
from django.db import models
from apps.core.utils.base62 import Base62


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDBaseModel(BaseModel):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=False)

    class Meta:
        abstract = True

    def get_short_uuid(self, length: int = 6) -> str:
        """UUID를 Base62로 인코딩한 짧은 문자열 반환"""
        return Base62.uuid_encode(self.uuid, length)
