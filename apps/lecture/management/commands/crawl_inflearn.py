import asyncio
from typing import Any, Dict, List

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.lecture.crawlers.inflearn_lecture_crawler_async import (
    InflearnLectureCrawlerAsync,
)
from apps.lecture.models import CrawledLecture


class Command(BaseCommand):

    def handle(self, *args: Any, **options: Any) -> None:
        crawler = InflearnLectureCrawlerAsync()
        db_data: List[Dict[str, Any]] = asyncio.run(crawler.crawl_and_process())

        with transaction.atomic():
            lectures: List[CrawledLecture] = [CrawledLecture(**data) for data in db_data]

            CrawledLecture.objects.bulk_create(
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
                unique_fields=["platform", "title", "instructor"],
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully crawled {len(lectures)} lectures from INFLEARN."))
