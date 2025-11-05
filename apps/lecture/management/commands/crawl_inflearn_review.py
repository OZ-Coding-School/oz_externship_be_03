import asyncio
from typing import Any, Dict, List

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.lecture.crawlers.inflearn_review_crawler_async import (
    InflearnReviewCrawlerAsync,
)
from apps.lecture.models import CrawledLecture, CrawledLectureReview


class Command(BaseCommand):

    def handle(self, *args: Any, **options: Any) -> None:
        lectures = CrawledLecture.objects.filter(platform="INFLEARN")
        course_id_to_lecture = {lecture.inflearn_course_id: lecture for lecture in lectures}
        course_ids = list(course_id_to_lecture.keys())

        if not course_ids:
            self.stdout.write(self.style.WARNING("강의를 먼저 크롤링하세요!"))
            return

        crawler = InflearnReviewCrawlerAsync()
        db_data: List[Dict[str, Any]] = asyncio.run(
            crawler.crawl_and_process_reviews(course_ids, max_concurrent_requests=15)  # type: ignore[arg-type]
        )

        with transaction.atomic():
            reviews = [
                CrawledLectureReview(
                    lecture=course_id_to_lecture[data["inflearn_course_id"]],
                    rating=data["rating"],
                    content=data["content"],
                    inflearn_review_id=data["inflearn_review_id"],
                )
                for data in db_data
                if data.get("inflearn_course_id") in course_id_to_lecture
            ]
            CrawledLectureReview.objects.bulk_create(
                reviews,
                update_conflicts=True,
                update_fields=["rating", "content"],
                unique_fields=["inflearn_review_id"],
            )

            self.stdout.write(self.style.SUCCESS(f"Successfully crawled {len(reviews)} reviews from INFLEARN."))
