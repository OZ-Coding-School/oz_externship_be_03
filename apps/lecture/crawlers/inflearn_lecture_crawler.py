import logging
from typing import Any, Dict, List, Optional

from apps.lecture.crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class LectureCrawler(BaseCrawler):
    VALID_CATEGORY_SLUGS = {
        "artificial-intelligence",
        "Applied-ai",
        "it-programming",
        "game-dev-all",
        "data-science",
        "it",
        "hardware",
        "design",
    }

    def __init__(self, auth_cookie: Optional[str] = None) -> None:
        super().__init__("https://course-api.inflearn.com/client/api/v1/course/search", auth_cookie)

    def crawl(self, page: int = 1, page_size: int = 100) -> Optional[Dict[str, Any]]:
        params = {
            "pageNumber": page,
            "pageSize": page_size,
            "sort": "POPULAR",
            "lang": "ko",
            "categorySlugs": ",".join(self.VALID_CATEGORY_SLUGS)  # ⭐ categories → categorySlugs
        }
        data = self.get_json(self.base_url, params)
        return data.get("data") if data and data.get("statusCode") == "OK" else None

    def get_lectures(self, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        """IT 카테고리 강의만 크롤링"""
        all_lectures, page = [], 1

        while True:
            data = self.crawl(page)
            if not data:
                break

            lectures = data.get("items", [])
            if not lectures:
                logger.info(f"페이지 {page}에 강의가 없어 종료")
                break

            all_lectures.extend(lectures)
            logger.info(f"페이지 {page} 완료 - {len(lectures)}개 수집")

            if max_pages and page >= max_pages:
                logger.info(f"최대 페이지({max_pages}) 도달")
                break

            page += 1

        logger.info(f"총 {len(all_lectures)}개 IT 강의 완료")
        return all_lectures


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    crawler = LectureCrawler()

    # ⭐ 파라미터 확인 추가
    params = {
        "pageNumber": 1,
        "pageSize": 100,
        "sort": "POPULAR",
        "lang": "ko",
        "categorySlugs": ",".join(crawler.VALID_CATEGORY_SLUGS)
    }

    print("\n=== 🔍 실제 요청 URL 확인 ===")
    print(f"Base URL: {crawler.base_url}")
    print(f"Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    full_url = f"{crawler.base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    print(f"\n전체 URL:\n{full_url}\n")
    print("=" * 80 + "\n")

    try:
        # 첫 페이지 정보
        first_page = crawler.crawl(page=1)
        if first_page:
            total_count = first_page.get("totalCount", 0)
            total_pages = first_page.get("totalPage", 0)
            print(f"\n=== categorySlugs 파라미터 테스트 ===")
            print(f"전체 IT 강의: {total_count}개")
            print(f"전체 페이지: {total_pages}페이지\n")

        # 전체 크롤링
        all_lectures = crawler.get_lectures()

        # 카테고리별 통계
        category_count = {}
        non_it_lectures = []

        for lecture in all_lectures:
            categories = lecture.get("course", {}).get("metadata", {}).get("categories", [])
            parent_slugs = [cat.get("parent", {}).get("slug", "") for cat in categories]

            # 카테고리 카운트
            for slug in parent_slugs:
                if slug:
                    category_count[slug] = category_count.get(slug, 0) + 1

            # IT 카테고리가 하나도 없는 강의 찾기
            if not any(slug in crawler.VALID_CATEGORY_SLUGS for slug in parent_slugs):
                non_it_lectures.append({
                    "title": lecture.get("course", {}).get("title", ""),
                    "categories": parent_slugs
                })

        print(f"\n✅ 총 {len(all_lectures)}개 강의 수집")

        if non_it_lectures:
            print(f"\n⚠️ 순수 비IT 강의 {len(non_it_lectures)}개 발견!")
            for lec in non_it_lectures[:5]:
                print(f"  - {lec['title']}")
                print(f"    카테고리: {lec['categories']}\n")
        else:
            print("\n✅ 모든 강의가 IT 카테고리를 포함하고 있습니다!")

        print("\n=== 카테고리별 강의 수 ===")
        for slug, count in sorted(category_count.items(), key=lambda x: x[1], reverse=True):
            status = "✅" if slug in crawler.VALID_CATEGORY_SLUGS else "❌"
            print(f"{status} {slug:30} : {count:4}개")

    finally:
        crawler.close()