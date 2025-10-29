import logging
from typing import Any, Dict, List, Optional

from base_crawler import BaseCrawler

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

    def crawl(self, page: int = 1, page_size: int = 20) -> Optional[Dict[str, Any]]:
        params = {"pageNumber": page, "pageSize": page_size, "sort": "POPULAR", "lang": "ko"}
        data = self.get_json(self.base_url, params)
        return data.get("data") if data and data.get("statusCode") == "OK" else None

    def is_it_category(self, lecture: Dict[str, Any]) -> bool:
        """IT 카테고리 여부 체크"""
        categories = lecture.get("course", {}).get("metadata", {}).get("categories", [])
        return any(
            cat.get("parent", {}).get("slug") in self.VALID_CATEGORY_SLUGS
            for cat in categories
        )

    def get_lectures(self, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        """IT 카테고리 강의만 크롤링"""
        all_lectures, page = [], 1
        while True:
            # 1단계: API에서 페이지 전체 데이터 가져오기
            data = self.crawl(page)  # 모든 카테고리 강의 (IT + 비IT)

            if not data:
                break

            # 2단계: items 추출
            lectures = data.get("items", [])  # 여기도 모든 카테고리 포함

            if not lectures:
                logger.info(f"페이지 {page}에 강의가 없어 종료")
                break

            # 3단계: IT 카테고리만 필터링 ⭐ 핵심!
            it_lectures = [lec for lec in lectures if self.is_it_category(lec)]

            # 4단계: 필터링된 IT 강의만 저장
            all_lectures.extend(it_lectures)  # IT만 추가됨

            logger.info(f"페이지 {page} 완료 - {len(lectures)}개 중 IT {len(it_lectures)}개 수집")

            if max_pages and page >= max_pages:
                logger.info(f"최대 페이지({max_pages}) 도달")
                break

            page += 1

        logger.info(f"총 {len(all_lectures)}개 IT 강의 완료")
        return all_lectures  # IT 강의만 리턴

    def transform_to_db_format(self, lecture: Dict[str, Any]) -> Dict[str, Any]:
        """크롤링 데이터를 DB 모델 형식으로 변환 (이미 IT 필터링된 데이터)"""
        course = lecture.get("course", {})
        instructor = lecture.get("instructor", {})
        list_price = lecture.get("listPrice", {})
        metadata = course.get("metadata", {})

        # 난이도 매핑
        level_map = {
            "BEGINNER": "EASY",
            "BASIC": "EASY",
            "INTERMEDIATE": "NORMAL",
            "ADVANCED": "HARD",
        }
        difficulty = level_map.get(metadata.get("level", "BASIC"), "EASY")

        # URL 생성
        slug = course.get("slug", "")
        url_link = f"https://www.inflearn.com/course/{slug}" if slug else ""

        # 걸러진 카테고리 정보 추출 (parent slug)
        categories = metadata.get("categories", [])
        category_slugs = [
            cat.get("parent", {}).get("slug", "")
            for cat in categories
            if cat.get("parent", {}).get("slug")
        ]

        return {
            "title": course.get("title", ""),
            "instructor": instructor.get("name", ""),
            "average_rating": float(course.get("star", 0.0)),
            "duration": metadata.get("runtimeSecond", 0) // 60,  # 초 -> 분 변환
            "difficulty": difficulty,
            "description": course.get("description", ""),
            "platform": "INFLEARN",
            "original_price": list_price.get("regularPrice", 0),
            "discount_price": list_price.get("payPrice", 0),
            "url_link": url_link,
            "thumbnail_img_url": course.get("thumbnailUrl", ""),
            "category_slugs": list(set(category_slugs)),  # 중복 제거
        }


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    crawler = LectureCrawler()
    try:
        # IT 강의 정보
        first_page = crawler.crawl(page=1)
        if first_page:
            total_pages = first_page.get("totalPage", 0)
            lectures = first_page.get("items", [])
            it_lectures = [lec for lec in lectures if crawler.is_it_category(lec)]
            estimated_it_count = first_page.get("totalCount", 0) * len(it_lectures) // len(lectures)

            print(f"\n전체 페이지: {total_pages}페이지")
            print(f"예상 IT 강의 수: 약 {estimated_it_count}개\n") #첫 페이지 비율로 추정한 값

        # 테스트 크롤링
        all_lectures = crawler.get_lectures(max_pages=3)
        transformed_lectures = [crawler.transform_to_db_format(lec) for lec in all_lectures]

        print(f"\n✅ {len(transformed_lectures)}개 IT 강의 수집 완료!")

        if transformed_lectures:
            print("\n=== 첫 번째 강의 ===")
            print(json.dumps(transformed_lectures[0], indent=2, ensure_ascii=False))

        # 전체 크롤링 (약 12분 소요)
        # all_lectures = crawler.get_lectures()
        # transformed_lectures = [crawler.transform_to_db_format(lec) for lec in all_lectures]
        # print(f"\n✅ {len(transformed_lectures)}개 IT 강의 수집 완료!")

    finally:
        crawler.close()