from argparse import ArgumentParser
from typing import Any, Dict, List

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
            # 1. LectureCrawler 호출(IT 강의만 필터링 된 상태)을 통한 IT 강의 데이터 수집
            self.stdout.write("크롤링 중...")
            it_lectures = crawler.get_lectures(max_pages=options.get("max_pages"))
            self.stdout.write(f"✓ IT 강의 {len(it_lectures)}개 수집")

            # 2. 수집된 데이터 -> DB 필드 구조로 포맷화.
            self.stdout.write("변환 중...")
            transformed = [crawler.transform_to_db_format(lec) for lec in it_lectures]
            self.stdout.write(f"✓ {len(transformed)}개 변환 완료")

            # 3. DB 저장
            saved_count = 0
            for lecture_data in transformed:
                try:
                    with transaction.atomic():
                        # 메인테이블(강의)과 보조테이블(카테고리) 분리
                        category_slugs = lecture_data.pop("category_slugs", [])
                        categories = [
                            Category.objects.get_or_create(slug=slug, defaults={"name": slug})[0]
                            for slug in category_slugs
                        ]

                        # 강의레코드 생성 (중복 체크 포함)
                        lecture, created = CrawledLecture.objects.update_or_create(
                            platform=lecture_data["platform"], title=lecture_data["title"], defaults=lecture_data
                        )

                        # 중간 테이블에 재조립 메인테이블(강의)-보조테이블(카테고리) > 다대다관계설정
                        lecture.categories.set(categories)  # lecture.categories의 정체: Related Manager
                        saved_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"저장 실패: {lecture_data.get('title')} - {e}"))

            self.stdout.write(self.style.SUCCESS(f"✓ 완료: {saved_count}개 저장"))

        finally:
            crawler.close()
