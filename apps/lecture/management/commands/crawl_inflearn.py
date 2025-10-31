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
            for data in db_data:
                CrawledLecture.objects.update_or_create(platform=data["platform"], title=data["title"], defaults=data)
