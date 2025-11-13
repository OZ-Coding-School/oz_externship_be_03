import asyncio
import logging
from typing import Any, Dict, List

from celery import Task, shared_task  # type: ignore
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore
from django.db import transaction
from django.utils.text import slugify

from apps.lecture.crawlers.inflearn_lecture_crawler_async import (
    InflearnLectureCrawlerAsync,
)
from apps.lecture.models import Category, CrawledLecture, LectureCategory
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import ModelTrainer

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=3600,  # 1시간 소프트 타임아웃
    time_limit=3900,  # 1시간 5분 하드 타임아웃
)  # type: ignore[misc]
def train_full_model_task(self: Task) -> Dict[str, Any]:
    """
    전체 모델 학습 비동기 작업

    타임아웃: 1시간 (soft) / 1시간 5분 (hard)
    재시도: 최대 3회, exponential backoff (60초 → 120초 → 240초)
    """
    try:
        logger.info("[CELERY][ALS] Full model training started")
        data_loader = DataLoader()
        trainer = ModelTrainer(data_loader)
        success = trainer.train_and_save_full_model()

        if not success:
            raise Exception("Model training failed")

        logger.info("[CELERY][ALS] Full model training completed")
        return {"status": "success", "message": "Full model training completed"}

    except SoftTimeLimitExceeded:
        logger.error("[CELERY][ALS] Training exceeded soft time limit (1 hour)")
        # retry()는 Retry 예외를 발생시켜 함수를 종료하므로 반환하지 않음
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=60 * (2**self.request.retries))

    except Exception as e:
        logger.error(f"[CELERY][ALS] Training failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=1800,  # 30분 소프트 타임아웃
    time_limit=2100,  # 35분 하드 타임아웃
)  # type: ignore[misc]
def partial_fit_model_task(self: Task) -> Dict[str, Any]:
    """
    증분 학습 비동기 작업

    타임아웃: 30분 (soft) / 35분 (hard)
    재시도: 최대 3회, exponential backoff (60초 → 120초 → 240초)
    """
    try:
        logger.info("[CELERY][ALS] Partial fit started")
        data_loader = DataLoader()
        trainer = ModelTrainer(data_loader)
        success = trainer.partial_fit_model_and_save()

        if not success:
            raise Exception("Partial fit failed")

        logger.info("[CELERY][ALS] Partial fit completed")
        return {"status": "success", "message": "Partial fit completed"}

    except SoftTimeLimitExceeded:
        logger.error("[CELERY][ALS] Partial fit exceeded soft time limit (30 minutes)")
        raise self.retry(exc=SoftTimeLimitExceeded(), countdown=60 * (2**self.request.retries))

    except Exception as e:
        logger.error(f"[CELERY][ALS] Partial fit failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))


@shared_task(name="crawl_inflearn_lectures")  # type: ignore[misc]
def crawl_inflearn_lectures() -> Dict[str, Any]:
    """
    인프런 강의 크롤링 Task
    매일 자정 실행
    """
    try:
        logger.info("인프런 강의 크롤링 시작")

        crawler = InflearnLectureCrawlerAsync()
        lectures_data: List[Dict[str, Any]] = asyncio.run(crawler.crawl_and_process(max_concurrent=10))

        if not lectures_data:
            logger.info("크롤링된 데이터 없음")
            return {"status": "failed", "count": 0}

        before_count = CrawledLecture.objects.filter(platform="INFLEARN").count()

        lectures: List[CrawledLecture] = []
        lecture_categories: dict[str, list[str]] = {}

        for data in lectures_data:
            lecture_categories[data["external_id"]] = data.pop("categories_raw", [])
            lectures.append(CrawledLecture(**data))

        created_lectures = CrawledLecture.objects.bulk_create(
            lectures,
            update_conflicts=True,
            update_fields=[
                "description",
                "average_rating",
                "duration",
                "difficulty",
                "original_price",
                "discount_price",
                "url_link",
                "thumbnail_img_url",
            ],
            unique_fields=["platform", "external_id"],
        )

        lecture_category_models = []

        for lecture in created_lectures:
            category_names = lecture_categories.get(lecture.external_id, [])  # type: ignore
            for ctg_name in category_names:
                if not ctg_name or not ctg_name.strip():
                    continue
                slug = slugify(ctg_name, allow_unicode=True)
                if not slug:
                    continue
                ctg, _ = Category.objects.get_or_create(slug=slug, defaults={"name": ctg_name})
                lecture_category_models.append(LectureCategory(lecture=lecture, category=ctg))

        LectureCategory.objects.bulk_create(
            lecture_category_models,
            ignore_conflicts=True,
        )

        after_count = CrawledLecture.objects.filter(platform="INFLEARN").count()
        created_count = after_count - before_count
        updated_count = len(lectures_data) - created_count

        logger.info(f"크롤링 완료 - 신규: {created_count}, 업데이트: {updated_count}")
        return {"status": "success", "created": created_count, "updated": updated_count, "total": len(lectures_data)}

    except Exception as e:
        logger.info(f"크롤링 실패: {e}", exc_info=True)
        return {"status": "error"}
