import asyncio
from typing import Any, Dict, List

from django.core.management.base import BaseCommand

from apps.lecture.crawlers.inflearn_lecture_crawler_async import (
    InflearnLectureCrawlerAsync,
)
from apps.lecture.models import Category, CrawledLecture, LectureCategory


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> None:
        crawler = InflearnLectureCrawlerAsync()
        db_data: List[Dict[str, Any]] = asyncio.run(crawler.crawl_and_process())
        lectures: List[CrawledLecture] = []
        lecture_categories: dict[str, list[str]] = {}

        for data in db_data:
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
                ctg, _ = Category.objects.get_or_create(name=ctg_name)
                lecture_category_models.append(LectureCategory(lecture=lecture, category=ctg))

        LectureCategory.objects.bulk_create(
            lecture_category_models,
            ignore_conflicts=True,
        )

        self.stdout.write(self.style.SUCCESS(f"Successfully crawled {len(created_lectures)} lectures from INFLEARN."))
