from django.conf import settings
from django.db import models


class SearchLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    q = models.CharField(max_length=255)  # 검색어
    filters = models.JSONField(default=dict, blank=True)  # 예: {"status":"OPEN","tags":["알고리즘"]}
    results_count = models.IntegerField(default=0)
    latency_ms = models.IntegerField(null=True, blank=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["q"]),
        ]

    def __str__(self) -> str:
        return f"{self.q} ({self.created_at:%Y-%m-%d %H:%M})"
