# apps/lecture/management/commands/inflearn_crawling.py
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "인프런 전체 크롤링 (카테고리→강의→리뷰)"

    def handle(self, *args: Any, **kwargs: Any) -> None:
        self.stdout.write("🚀 전체 크롤링 시작\n")

        call_command("crawl_inflearn_ctg")
        call_command("crawl_inflearn")
        call_command("crawl_inflearn_review")

        self.stdout.write(self.style.SUCCESS("\n✨ 전체 크롤링 완료!"))
