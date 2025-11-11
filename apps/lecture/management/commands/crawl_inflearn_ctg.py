from typing import Any

from django.core.management.base import BaseCommand

from apps.lecture.crawlers.inflearn_ctg import InflearnCategoryCrawler
from apps.lecture.models import Category


class Command(BaseCommand):
    help = "인플런 카테고리 크롤링 및 DB 저장"

    def handle(self, *args: Any, **options: Any) -> None:
        crawler = InflearnCategoryCrawler()
        categories = crawler.crawl()

        for ctg in categories:
            Category.objects.update_or_create(slug=ctg["slug"], defaults={"name": ctg["title"]})

        self.stdout.write(self.style.SUCCESS(f"✅ {len(categories)}개 카테고리 저장 완료"))
