import logging
from typing import Any, Dict, List, Optional

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class LectureCrawler(BaseCrawler):
    def __init__(self, auth_cookie: Optional[str] = None) -> None:
        super().__init__("https://course-api.inflearn.com/client/api/v1/course/search", auth_cookie)

    def crawl(self, page: int = 1, page_size: int = 20) -> Optional[Dict[str, Any]]:
        params = {"pageNumber": page, "pageSize": page_size, "sort": "POPULAR", "lang": "ko"}
        data = self.get_json(self.base_url, params)
        return data.get("data") if data and data.get("statusCode") == "OK" else None

    def get_lectures(self, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
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

        logger.info(f"총 {len(all_lectures)}개 완료")
        return all_lectures

    def transform_to_db_format(self, lecture: Dict[str, Any]) -> Dict[str, Any]:
        """크롤링 데이터를 DB 모델 형식으로 변환"""
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

        # IT 관련 카테고리만 필터링
        valid_ctg_slugs = {
            "artificial-intelligence",
            "Applied-ai",
            "it-programming",
            "game-dev-all",
            "data-science",
            "it",
            "hardware",
            "design",
        }

        categories = metadata.get("categories", [])
        filtered_slugs = []
        for category in categories:
            parent_slug = category.get("parent", {}).get("slug", "")
            if parent_slug in valid_ctg_slugs:
                filtered_slugs.append(parent_slug)

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
            "category_slugs": list(set(filtered_slugs)),  # 중복 제거
        }


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    crawler = LectureCrawler()
    try:
        # 전체 개수 확인 (첫 페이지만으로)
        print("\n=== 전체 강의 개수 확인 ===")
        first_page = crawler.crawl(page=1)
        if first_page:
            total_count = first_page.get("totalCount", 0)
            total_pages = first_page.get("totalPage", 0)
            page_size = first_page.get("pageSize", 0)
            print(f"전체 강의 수: {total_count}개")
            print(f"전체 페이지: {total_pages}페이지")
            print(f"페이지당 강의: {page_size}개")
            print(f"예상 크롤링 시간: 약 {total_pages * 3 / 60:.1f}분")

            # IT 카테고리 필터링 확인 (첫 페이지 기준)
            lectures = first_page.get("items", [])
            transformed = [crawler.transform_to_db_format(lec) for lec in lectures]
            filtered = [t for t in transformed if t.get("category_slugs")]
            print(f"\n[첫 페이지 기준] 전체: {len(lectures)}개 → IT 카테고리: {len(filtered)}개")
            print(f"예상 IT 강의 수: 약 {total_count * len(filtered) // len(lectures)}개")

        print("\n=== 첫 페이지 크롤링 & 변환 ===")
        data = crawler.crawl(page=1)
        if data:
            lectures = data.get("items", [])
            print(f"강의 {len(lectures)}개 수집")

            # DB 형식으로 변환
            transformed_lectures = [crawler.transform_to_db_format(lec) for lec in lectures]
            print(f"{len(transformed_lectures)}개 강의 DB 형식 변환 완료")

            # 첫 번째 강의 예시 출력
            if transformed_lectures:
                print("\n=== 변환된 첫 번째 강의 ===")
                print(json.dumps(transformed_lectures[0], indent=2, ensure_ascii=False))
        else:
            print("응답 없음")

        # 전체 크롤링 필요시 아래 주석 해제
        # print("\n=== 전체 강의 크롤링 시작 ===")
        # all_lectures = crawler.get_lectures()  # 249페이지 전부 (약 12분 소요)
        # # all_lectures = crawler.get_lectures(max_pages=10)  # 10페이지만
        #
        # # DB 형식으로 변환
        # transformed_lectures = [crawler.transform_to_db_format(lec) for lec in all_lectures]
        # print(f"\n총 {len(transformed_lectures)}개 강의 변환 완료!")
        #
        # # 실제로 수집된 개수 확인
        # print(f"목표: {total_count}개")
        # print(f"수집: {len(all_lectures)}개")
        # print(f"변환: {len(transformed_lectures)}개")

    finally:
        crawler.close()
