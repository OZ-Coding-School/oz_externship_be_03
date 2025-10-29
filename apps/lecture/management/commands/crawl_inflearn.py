from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.lecture.crawlers.inflearn_lecture_crawler import LectureCrawler
from apps.lecture.models import Category, CrawledLecture


class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--max-pages", type=int, default=None, help="최대 페이지 수")

    def handle(self, *args: Any, **options: Any) -> None:
        crawler = LectureCrawler()

        try:
            # 1. 크롤링
            self.stdout.write("크롤링 중...")
            all_lectures = crawler.get_lectures(max_pages=options.get("max_pages"))
            self.stdout.write(f"✓ {len(all_lectures)}개 수집")

            # 2. 변환
            transformed = [crawler.transform_to_db_format(lec) for lec in all_lectures]

            # 3. IT 필터링
            it_lectures = [t for t in transformed if t.get("category_slugs")]
            self.stdout.write(f"✓ IT 강의 {len(it_lectures)}개")

            # 4. DB 저장
            saved_count = 0
            for lecture_data in it_lectures:
                try:
                    with transaction.atomic():
                        # 카테고리 처리
                        category_slugs = lecture_data.pop("category_slugs", [])
                        categories = [
                            Category.objects.get_or_create(slug=slug, defaults={"name": slug})[0]
                            for slug in category_slugs
                        ]

                        # CrawledLecture 생성 (중복 체크 포함)
                        lecture, created = CrawledLecture.objects.update_or_create(
                            platform=lecture_data["platform"], title=lecture_data["title"], defaults=lecture_data
                        )

                        # 카테고리 연결
                        lecture.categories.set(categories)
                        saved_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"저장 실패: {lecture_data.get('title')} - {e}"))

            self.stdout.write(self.style.SUCCESS(f"✓ 완료: {saved_count}개 저장"))

        finally:
            crawler.close()
