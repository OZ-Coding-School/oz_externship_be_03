import asyncio
from typing import Any

from django.core.management.base import BaseCommand

from apps.lecture.crawlers.inflearn_review_crawler_async import (
    InflearnReviewCrawlerAsync,
)


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> None:
        crawler = InflearnReviewCrawlerAsync()
        crawled_review_len = asyncio.run(crawler.crawl_and_process_reviews())

        self.stdout.write(self.style.SUCCESS(f"Successfully crawled {crawled_review_len} reviews from INFLEARN."))
