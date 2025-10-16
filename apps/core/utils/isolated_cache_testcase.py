import copy
import uuid

from django.conf import settings
from django.test import override_settings
from django_redis import get_redis_connection  # type: ignore
from rest_framework.test import APITestCase


class IsolatedRedisTestClient(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        cache_settings = copy.deepcopy(settings.CACHES)
        # 각 테스트마다 고유한 UUID로 KEY_PREFIX를 설정
        cache_settings["default"]["KEY_PREFIX"] = f"test_{uuid.uuid4().hex}_"
        cache_settings["default"]["LOCATION"] = f"redis://{settings.REDIS_HOST}:6379/15"
        self._isolated_cache_settings_override = override_settings(CACHES=cache_settings)
        self._isolated_cache_settings_override.enable()
        self.redis_client = get_redis_connection("default")

    def tearDown(self) -> None:
        self._isolated_cache_settings_override.disable()
        self.redis_client.flushdb()  # 현재 DB만 초기화
        super().tearDown()
