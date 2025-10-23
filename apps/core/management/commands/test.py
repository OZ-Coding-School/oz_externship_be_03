from typing import Any

import redis.client
from django.conf import settings
from django.core.management.commands.test import Command as TestCommand


class Command(TestCommand):
    def handle(self, *test_labels: Any, **options: Any) -> None:
        self.teardown_redis()
        super().handle(*test_labels, **options)
        self.teardown_redis()

    @staticmethod
    def teardown_redis() -> None:
        redis.client.Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/15").flushdb()
