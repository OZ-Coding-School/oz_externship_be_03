import asyncio
from typing import Any, Awaitable, Dict, List, Optional

import aiohttp

from .inflearn_lecture_crawler_async import InflearnLectureCrawlerAsync


class InflearnReviewCrawlerAsync(InflearnLectureCrawlerAsync):

    async def fetch_review_page(
        self, session: aiohttp.ClientSession, course_id: int, page_number: int
    ) -> Optional[Dict[str, Any]]:

        base_url = f"https://ucc-api.inflearn.com/client/api/v1/reviews/course/{course_id}"
        parameters = f"id={course_id}&pageNumber={page_number}&pageSize=3&sort=RECOMMEND&lang=ko"

        url = base_url + "?" + parameters

        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()

                result: Dict[str, Any] = await response.json()
                result["course_id"] = course_id
                return result

        except Exception:
            return None

    async def get_all_course_reviews(
        self, all_course_ids: List[int], max_concurrent_requests: int = 15
    ) -> List[Dict[str, Any]]:

        semaphore = asyncio.Semaphore(max_concurrent_requests)

        async with aiohttp.ClientSession() as session:

            async def fetch_with_limit(course_id: int) -> Optional[Dict[str, Any]]:
                async with semaphore:
                    return await self.fetch_review_page(session, course_id, page_number=1)

            tasks: List[Awaitable[Optional[Dict[str, Any]]]] = [
                fetch_with_limit(course_id) for course_id in all_course_ids
            ]

            results: List[Optional[Dict[str, Any]]] = await asyncio.gather(*tasks)

            return [res for res in results if res is not None]

    def convert_reviews_to_db_format(self, raw_review_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        converted_reviews: List[Dict[str, Any]] = []

        rating_map = {
            5: "5_OUT_OF_5_STARS",
            4: "4_OUT_OF_5_STARS",
            3: "3_OUT_OF_5_STARS",
            2: "2_OUT_OF_5_STARS",
            1: "1_OUT_OF_5_STARS",
        }

        for response in raw_review_data:
            course_id = response.get("course_id")
            items = response.get("data", {}).get("items", [])

            for review in items:
                rating = review.get("star", 5)
                review_info: Dict[str, Any] = {
                    "inflearn_course_id": course_id,
                    "inflearn_review_id": review.get("id"),
                    "rating": rating_map.get(rating, "5_OUT_OF_5_STARS"),
                    "content": review.get("body", ""),
                }
                converted_reviews.append(review_info)

        return converted_reviews

    async def crawl_and_process_reviews(
        self, all_course_ids: List[int], max_concurrent_requests: int = 15
    ) -> List[Dict[str, Any]]:

        raw_data = await self.get_all_course_reviews(all_course_ids, max_concurrent_requests)
        db_formatted_data = self.convert_reviews_to_db_format(raw_data)
        return db_formatted_data
