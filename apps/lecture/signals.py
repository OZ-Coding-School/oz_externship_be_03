import logging
from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.lecture.models.lecture import CrawledLecture
from apps.lecture.services.recommendation_service.constants import (
    LECTURE_METADATA_CACHE_KEY,
    POPULAR_LECTURE_CACHE_KEY,
)

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=CrawledLecture)
def invalidate_lecture_cache(sender: type[CrawledLecture], instance: CrawledLecture, **kwargs: Any) -> None:
    """
    강의 정보 변경 시 관련 캐시 무효화

    처리: 강의 메타데이터 + 인기 강의 캐시 삭제
    트리거: post_save (생성/수정), post_delete (삭제)
    실패 처리: 로그만 출력, 프로세스 계속
    """
    try:
        # 강의별 메타데이터 캐시 무효화
        cache_key: str = LECTURE_METADATA_CACHE_KEY.format(instance.id)
        cache.delete(cache_key)

        # 인기 강의 캐시 무효화 (평점 변경 시 순위 영향)
        cache.delete(POPULAR_LECTURE_CACHE_KEY)

        logger.info(f"[CACHE_INVALIDATION] Lecture {instance.id} ({instance.title}) " f"cache invalidated")
    except Exception as e:
        logger.error(f"[CACHE_INVALIDATION] Failed for lecture {instance.id}: {e}")
