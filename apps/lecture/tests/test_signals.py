from unittest import mock

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.test import TestCase, tag

from apps.lecture.models.lecture import CrawledLecture
from apps.lecture.services.recommendation_service.constants import (
    LECTURE_METADATA_CACHE_KEY,
    POPULAR_LECTURE_CACHE_KEY,
)
from apps.lecture.signals import invalidate_lecture_cache


class BaseSignalSetup(TestCase):
    """시그널 테스트를 위한 베이스 클래스"""

    def setUp(self) -> None:
        """시그널 연결 상태 저장 및 캐시 초기화"""
        super().setUp()
        self.pre_signals = (
            len(post_save.receivers),
            len(post_delete.receivers),
        )
        cache.clear()
        self.addCleanup(cache.clear)

    def tearDown(self) -> None:
        """시그널이 제대로 정리되었는지 확인"""
        super().tearDown()
        post_signals = (
            len(post_save.receivers),
            len(post_delete.receivers),
        )
        self.assertEqual(self.pre_signals, post_signals)


@tag("signals", "cache")
class InvalidateLectureCacheSignalTests(BaseSignalSetup):
    """invalidate_lecture_cache 시그널 핸들러 테스트"""

    LECTURE_METADATA_CACHE_KEY_TEMPLATE: str
    POPULAR_LECTURE_CACHE_KEY_VALUE: str

    @classmethod
    def setUpClass(cls) -> None:
        """클래스 레벨 상수 설정"""
        super().setUpClass()
        cls.LECTURE_METADATA_CACHE_KEY_TEMPLATE = LECTURE_METADATA_CACHE_KEY
        cls.POPULAR_LECTURE_CACHE_KEY_VALUE = POPULAR_LECTURE_CACHE_KEY

    def setUp(self) -> None:
        """각 테스트 전에 공통 강의 객체 생성"""
        super().setUp()
        self.lecture = CrawledLecture.objects.create(
            title="테스트 강의",
            instructor="테스트 강사",
            platform=CrawledLecture.PlatformEnum.UDEMY,
            duration=120,
            difficulty=CrawledLecture.DifficultyEnum.NORMAL,
            description="테스트 설명",
            url_link="https://test.com/lecture",
            original_price=50000,
            discount_price=30000,
        )

    def test_cache_invalidation_on_lecture_save(self) -> None:
        """강의 저장 시 강의 메타데이터와 인기 강의 캐시 무효화"""
        cache_key = self.LECTURE_METADATA_CACHE_KEY_TEMPLATE.format(self.lecture.id)
        cache.set(cache_key, {"title": "테스트 강의"})
        cache.set(self.POPULAR_LECTURE_CACHE_KEY_VALUE, ["lecture1", "lecture2"])

        self.lecture.title = "수정된 강의"
        self.lecture.save()

        self.assertIsNone(cache.get(cache_key))
        self.assertIsNone(cache.get(self.POPULAR_LECTURE_CACHE_KEY_VALUE))

    def test_cache_invalidation_on_lecture_delete(self) -> None:
        """강의 삭제 시 강의 메타데이터와 인기 강의 캐시 무효화"""
        cache_key = self.LECTURE_METADATA_CACHE_KEY_TEMPLATE.format(self.lecture.id)
        cache.set(cache_key, {"title": "테스트 강의"})
        cache.set(self.POPULAR_LECTURE_CACHE_KEY_VALUE, ["lecture1", "lecture2"])

        self.lecture.delete()

        self.assertIsNone(cache.get(cache_key))
        self.assertIsNone(cache.get(self.POPULAR_LECTURE_CACHE_KEY_VALUE))

    def test_cache_invalidation_on_lecture_create(self) -> None:
        """강의 생성 시 인기 강의 캐시 무효화"""
        cache.set(self.POPULAR_LECTURE_CACHE_KEY_VALUE, ["lecture1", "lecture2"])

        CrawledLecture.objects.create(
            title="새 강의",
            instructor="새 강사",
            platform=CrawledLecture.PlatformEnum.INFLEARN,
            duration=90,
            difficulty=CrawledLecture.DifficultyEnum.EASY,
            description="새 강의 설명",
            url_link="https://test.com/new-lecture",
            original_price=40000,
            discount_price=20000,
        )

        self.assertIsNone(cache.get(self.POPULAR_LECTURE_CACHE_KEY_VALUE))

    def test_cache_invalidation_logging_success(self) -> None:
        """캐시 무효화 성공 시 INFO 로그 기록"""
        with self.assertLogs("apps.lecture.signals", level="INFO") as cm:
            self.lecture.title = "수정된 강의"
            self.lecture.save()

            log_messages = [record.getMessage() for record in cm.records]
            self.assertTrue(
                any(
                    "[CACHE_INVALIDATION]" in msg
                    and str(self.lecture.id) in msg
                    and "수정된 강의" in msg
                    and "cache invalidated" in msg
                    for msg in log_messages
                ),
                f"예상된 캐시 무효화 로그를 찾을 수 없음: {log_messages}",
            )

    def test_cache_invalidation_exception_handling(self) -> None:
        """캐시 삭제 중 예외 발생 시 로그만 기록하고 프로세스 계속"""
        with mock.patch("apps.lecture.signals.cache.delete", side_effect=Exception("캐시 오류")):
            with self.assertLogs("apps.lecture.signals", level="ERROR") as cm:
                self.lecture.title = "수정된 강의"
                self.lecture.save()

                log_messages = [record.getMessage() for record in cm.records]
                self.assertTrue(
                    any(
                        "[CACHE_INVALIDATION]" in msg and "Failed for lecture" in msg and str(self.lecture.id) in msg
                        for msg in log_messages
                    ),
                    f"예상된 에러 로그를 찾을 수 없음: {log_messages}",
                )

    def test_multiple_lectures_cache_isolation(self) -> None:
        """여러 강의의 캐시가 독립적으로 무효화됨"""
        lecture2 = CrawledLecture.objects.create(
            title="두 번째 강의",
            instructor="두 번째 강사",
            platform=CrawledLecture.PlatformEnum.INFLEARN,
            duration=150,
            difficulty=CrawledLecture.DifficultyEnum.HARD,
            description="두 번째 강의 설명",
            url_link="https://test.com/lecture2",
            original_price=60000,
            discount_price=40000,
        )

        cache_key1 = self.LECTURE_METADATA_CACHE_KEY_TEMPLATE.format(self.lecture.id)
        cache_key2 = self.LECTURE_METADATA_CACHE_KEY_TEMPLATE.format(lecture2.id)
        cache.set(cache_key1, {"title": "강의 1"})
        cache.set(cache_key2, {"title": "강의 2"})
        cache.set(self.POPULAR_LECTURE_CACHE_KEY_VALUE, ["lecture1", "lecture2"])

        self.lecture.title = "수정된 강의 1"
        self.lecture.save()

        self.assertIsNone(cache.get(cache_key1))
        self.assertIsNone(cache.get(self.POPULAR_LECTURE_CACHE_KEY_VALUE))
        self.assertIsNotNone(cache.get(cache_key2))

    def test_signal_disconnect_and_reconnect(self) -> None:
        """시그널 연결 해제 시 캐시 무효화가 발생하지 않음"""
        cache_key = self.LECTURE_METADATA_CACHE_KEY_TEMPLATE.format(self.lecture.id)
        cache.set(cache_key, {"title": "테스트"})

        post_save.disconnect(invalidate_lecture_cache, sender=CrawledLecture)
        self.lecture.title = "수정됨"
        self.lecture.save()

        self.assertIsNotNone(cache.get(cache_key))

        post_save.connect(invalidate_lecture_cache, sender=CrawledLecture)
        self.addCleanup(post_save.disconnect, invalidate_lecture_cache, sender=CrawledLecture)

    def test_cache_invalidation_in_transaction(self) -> None:
        """트랜잭션 내에서 캐시 무효화가 올바르게 작동"""
        cache_key = self.LECTURE_METADATA_CACHE_KEY_TEMPLATE.format(self.lecture.id)
        cache.set(cache_key, {"title": "테스트"})

        with transaction.atomic():
            self.lecture.title = "수정됨"
            self.lecture.save()

        self.assertIsNone(cache.get(cache_key))
