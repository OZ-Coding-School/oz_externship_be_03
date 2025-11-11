import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from .inflearn_ctg import InflearnCategoryCrawler

logger = logging.getLogger(__name__)


class InflearnLectureCrawlerAsync(InflearnCategoryCrawler):
    valid_ctg_slugs: List[str] = [
        "artificial-intelligence",
        "Applied-ai",
        "it-programming",
        "game-dev-all",
        "data-science",
        "it",
        "hardware",
        "design",
    ]

    async def fetch_page(self, session: aiohttp.ClientSession, page_number: int) -> Optional[Dict[str, Any]]:
        base_url = "https://course-api.inflearn.com/client/api/v1/course/search"
        parameters = f"pageNumber={page_number}&pageSize=100&sort=POPULAR&lang=ko&categories=" + ",".join(
            self.valid_ctg_slugs
        )
        url = base_url + "?" + parameters

        try:
            await asyncio.sleep(0.2)

            timeout = aiohttp.ClientTimeout(total=30)
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()
                result: Dict[str, Any] = await response.json()
                return result

        except asyncio.TimeoutError:
            logger.error(f"{page_number} 타임아웃 - 스킵")
            return None

        except aiohttp.ClientResponseError as e:
            logger.error(f"{page_number} HTTP 에러 {e.status} - 스킵")
            return None

        except aiohttp.ClientError as e:
            logger.error(f"{page_number} 네트워크 에러 - 스킵")
            return None

        except Exception as e:
            logger.error(f"{page_number} 예상치 못한 에러: {e} - 스킵")
            return None

    async def crawl_all_pages_async(self, max_concurrent: int = 5, chunk_size: int = 50) -> List[Dict[str, Any]]:

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_limit(session: aiohttp.ClientSession, page_num: int) -> Optional[Dict[str, Any]]:
            async with semaphore:
                return await self.fetch_page(session, page_num)

        async with aiohttp.ClientSession() as session:

            first_response = await self.fetch_page(session, 1)

            if not first_response:
                return []

            total_count = first_response.get("data", {}).get("totalCount", 0)
            total_pages = (total_count // 100) + (1 if total_count % 100 else 0)

            all_raw_data: List[Dict[str, Any]] = first_response.get("data", {}).get("items", [])

            if total_pages > 1:
                remaining_pages = list(range(2, total_pages + 1))

                for i in range(0, len(remaining_pages), chunk_size):
                    chunk = remaining_pages[i : i + chunk_size]

                    tasks = [fetch_with_limit(session, page) for page in chunk]
                    responses = await asyncio.gather(*tasks)

                    for response_data in responses:
                        if response_data:
                            lecture_items: List[Dict[str, Any]] = response_data.get("data", {}).get("items", [])
                            all_raw_data.extend(lecture_items)

                    if i + chunk_size < len(remaining_pages):
                        await asyncio.sleep(0.1)

            return all_raw_data

    def filter_data(self, raw_lecture_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        filtered_data: List[Dict[str, Any]] = []

        unique_ids: set[int] = set()

        for item in raw_lecture_items:
            course: Dict[str, Any] = item.get("course", {})
            course_id: int | None = course.get("id")

            if not course_id or course_id in unique_ids:
                continue

            unique_ids.add(course_id)

            filtered_data.append(item)

        return filtered_data

    def convert_to_db_format(self, filtered_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        processed_data: List[Dict[str, Any]] = []

        for item in filtered_items:
            course: Dict[str, Any] = item.get("course", {})
            instructor: Dict[str, Any] = item.get("instructor", {})
            metadata: Dict[str, Any] = course.get("metadata", {})
            list_price: Dict[str, Any] = item.get("listPrice", {})
            slug: str = course.get("slug", "")

            # 난이도 매핑
            level_map: Dict[str, str] = {
                "BASIC": "EASY",
                "BEGINNER": "EASY",
                "INTERMEDIATE": "NORMAL",
                "ADVANCED": "HARD",
            }
            api_level: str = metadata.get("level", "BEGINNER")
            difficulty: str = level_map.get(api_level, "EASY")

            # 시간 변환
            runtime_seconds: int = course.get("runtimeSecond", 0)
            duration_minutes: int = runtime_seconds // 60

            lecture_info: Dict[str, Any] = {
                "external_id": course.get("id"),
                "title": course.get("title", ""),
                "instructor": instructor.get("name", ""),
                "average_rating": round(course.get("star", 0.0), 2),
                "duration": duration_minutes,
                "difficulty": difficulty,
                "description": course.get("description", "강의 설명이 없습니다."),
                "platform": "INFLEARN",
                "original_price": list_price.get("regularPrice", 0),
                "discount_price": list_price.get("payPrice", 0),
                "url_link": f"https://www.inflearn.com/course/{slug}" if slug else "",
                "thumbnail_img_url": course.get("thumbnailUrl"),
                "skill_slugs": [tag["slug"] for tag in metadata.get("skillTags", [])],
            }
            processed_data.append(lecture_info)

        return processed_data

    async def crawl_and_process(self, max_concurrent: int = 10) -> List[Dict[str, Any]]:
        raw_data = await self.crawl_all_pages_async(max_concurrent)
        filtered_data = self.filter_data(raw_data)
        db_data = self.convert_to_db_format(filtered_data)
        return db_data
