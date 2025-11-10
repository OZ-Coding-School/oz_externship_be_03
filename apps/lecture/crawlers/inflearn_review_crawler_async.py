import asyncio
import logging
from typing import Any, Awaitable, Dict, List, Optional

import aiohttp
from channels.db import database_sync_to_async
from django.db import transaction

from ..models import CrawledLecture, CrawledLectureReview
from .inflearn_lecture_crawler_async import InflearnLectureCrawlerAsync

logger = logging.getLogger(__name__)


class InflearnReviewCrawlerAsync(InflearnLectureCrawlerAsync):

    async def fetch_review_page(
        self, session: aiohttp.ClientSession, external_id: int, lecture_id: int, page_number: int
    ) -> Optional[Dict[str, Any]]:

        base_url = f"https://ucc-api.inflearn.com/client/api/v1/reviews/course/{external_id}"
        parameters = f"id={external_id}&pageNumber={page_number}&pageSize=3&sort=RECOMMEND&lang=ko"

        url = base_url + "?" + parameters

        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()

                result: Dict[str, Any] = await response.json()
                result["lecture_id"] = lecture_id
                return result

        except Exception:
            return None

    async def get_all_lecture_reviews(
        self, lecture_id_map: dict[int, int], max_concurrent_requests: int = 15
    ) -> List[Dict[str, Any]]:

        semaphore = asyncio.Semaphore(max_concurrent_requests)

        async with aiohttp.ClientSession() as session:

            async def fetch_with_limit(external_id: int, lecture_id: int) -> Optional[Dict[str, Any]]:
                async with semaphore:
                    return await self.fetch_review_page(session, external_id, lecture_id, page_number=1)

            tasks: List[Awaitable[Optional[Dict[str, Any]]]] = [
                fetch_with_limit(external_id, lecture_id_map[external_id]) for external_id in lecture_id_map.keys()
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
            lecture_id = response.get("lecture_id")
            items = response.get("data", {}).get("items", [])

            for review in items:
                rating = review.get("star", 5)
                review_info: Dict[str, Any] = {
                    "lecture_id": lecture_id,
                    "external_id": review.get("id"),
                    "rating": rating_map.get(rating, "5_OUT_OF_5_STARS"),
                    "content": review.get("body", ""),
                }
                converted_reviews.append(review_info)

        return converted_reviews

    async def crawl_and_process_reviews(self, max_concurrent_requests: int = 15) -> int:
        lectures = await database_sync_to_async(
            lambda: list(CrawledLecture.objects.filter(platform="INFLEARN").values("external_id", "id"))
        )()

        if not lectures:
            logger.warning("No lectures found.")
            return 0

        lecture_id_map = {lecture["external_id"]: lecture["id"] for lecture in lectures}

        raw_data = await self.get_all_lecture_reviews(lecture_id_map, max_concurrent_requests)
        db_formatted_data = self.convert_reviews_to_db_format(raw_data)

        reviews = [CrawledLectureReview(**data) for data in db_formatted_data]
        await CrawledLectureReview.objects.abulk_create(
            reviews,
            update_conflicts=True,
            update_fields=["rating", "content"],
            unique_fields=["lecture_id", "external_id"],
        )

        return len(reviews)
