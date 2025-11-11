import asyncio
from typing import Any, Dict, List

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.lecture.crawlers.inflearn_lecture_crawler_async import (
    InflearnLectureCrawlerAsync,
)
from apps.lecture.models import Category, CrawledLecture


class Command(BaseCommand):

    def handle(self, *args: Any, **options: Any) -> None:
        crawler = InflearnLectureCrawlerAsync()
        db_data: List[Dict[str, Any]] = asyncio.run(crawler.crawl_and_process())

        with transaction.atomic():
            # skill_slugs 분리
            skill_slugs_map = {data["external_id"]: data.pop("skill_slugs", []) for data in db_data}

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
                unique_fields=["platform", "external_id"],
            )

            # 카테고리 연결
            for lecture in CrawledLecture.objects.filter(external_id__in=skill_slugs_map.keys()):
                skill_slugs = skill_slugs_map.get(lecture.external_id, [])
                if skill_slugs:
                    categories = Category.objects.filter(slug__in=skill_slugs)
                    lecture.categories.set(categories)

            self.stdout.write(self.style.SUCCESS(f"Successfully crawled {len(lectures)} lectures from INFLEARN."))
