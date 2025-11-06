from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

from django.test import TestCase

from apps.lecture.models import CrawledLecture
from apps.lecture.tasks import crawl_inflearn_lectures
from config.celery import app


class CrawlLecturesTaskTest(TestCase):
    """task 테스트"""

    def setUp(self) -> None:
        self.mock_lecture_data: List[Dict[str, Any]] = [
            {
                "title": "Python 기초",
                "instructor": "홍길동",
                "average_rating": 4.5,
                "duration": 600,
                "difficulty": "EASY",
                "description": "Python 기초 강의",
                "platform": "INFLEARN",
                "original_price": 50000,
                "discount_price": 30000,
                "url_link": "https://www.inflearn.com/python",
                "thumbnail_img_url": "https://inflearn.com/thumb.jpg",
            }
        ]

    @patch("apps.lecture.tasks.InflearnLectureCrawlerAsync")
    def test_create_crawl_lectures(self, mock_crawler_class: Any) -> None:
        """신규 강의 생성"""
        mock_instance = mock_crawler_class.return_value
        mock_instance.crawl_and_process = AsyncMock(return_value=self.mock_lecture_data)

        result = crawl_inflearn_lectures()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(CrawledLecture.objects.count(), 1)

    @patch("apps.lecture.tasks.InflearnLectureCrawlerAsync")
    def test_update_crawl_lectures(self, mock_crawler_class: Any) -> None:
        """기존 강의 업데이트"""
        CrawledLecture.objects.create(
            title="Python 기초",
            instructor="홍길동",
            average_rating=2.5,
            duration=6000,
            difficulty="HARD",
            description="Python 기초초 강의",
            platform="INFLEARN",
            original_price=500000,
            discount_price=300000,
            url_link="https://www.inflearn.com/superpython",
            thumbnail_img_url="https://inflearn.com/superthumb.jpg",
        )

        mock_instance = mock_crawler_class.return_value
        mock_instance.crawl_and_process = AsyncMock(return_value=self.mock_lecture_data)

        result = crawl_inflearn_lectures()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(CrawledLecture.objects.count(), 1)

        lecture = CrawledLecture.objects.first()
        assert lecture is not None
        self.assertEqual(lecture.discount_price, 30000)

    @patch("apps.lecture.tasks.InflearnLectureCrawlerAsync")
    def test_crawl_empty_data(self, mock_crawler_class: Any) -> None:
        """데이터 없음"""
        mock_instance = mock_crawler_class.return_value
        mock_instance.crawl_and_process = AsyncMock(return_value=[])

        result = crawl_inflearn_lectures()

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["count"], 0)
        self.assertEqual(CrawledLecture.objects.count(), 0)

    @patch("apps.lecture.tasks.InflearnLectureCrawlerAsync")
    def test_crawl_exception(self, mock_crawler_class: Any) -> None:
        """크롤링 실패"""
        mock_instance = mock_crawler_class.return_value
        mock_instance.crawl_and_process = AsyncMock(side_effect=Exception("임시 오류"))

        result = crawl_inflearn_lectures()

        self.assertEqual(result["status"], "error")
        self.assertEqual(CrawledLecture.objects.count(), 0)


class CeleryBeatScheduleTest(TestCase):
    """Celery Beat 스케줄 테스트"""

    def test_crawl_inflearn_schedule_registered(self) -> None:
        """스케줄 등록 확인"""

        schedule = app.conf.beat_schedule

        self.assertIn("crawl-inflearn-lectures-daily", schedule)

    def test_crawl_inflearn_schedule_configuration(self) -> None:
        """인프런 크롤링 스케줄 설정 체크"""

        schedule = app.conf.beat_schedule["crawl-inflearn-lectures-daily"]

        # Task 이름 검증
        self.assertEqual(schedule["task"], "crawl_inflearn_lectures")

        # Crontab 설정 검증
        cron = schedule["schedule"]
        self.assertEqual(cron.hour, {0})
        self.assertEqual(cron.minute, {0})
