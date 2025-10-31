import asyncio
import aiohttp
from .inflearn_ctg import InflearnCategoryCrawler


class InflearnLectureCrawlerAsync(InflearnCategoryCrawler):
    valid_ctg_slugs = [
        "artificial-intelligence",
        "Applied-ai",
        "it-programming",
        "game-dev-all",
        "data-science",
        "it",
        "hardware",
        "design",
    ]

    async def fetch_page(self, session, page_number):
        base_url = "https://course-api.inflearn.com/client/api/v1/course/search"
        parameters = f"pageNumber={page_number}&pageSize=100&sort=POPULAR&lang=ko&categories=" + ",".join(
            self.valid_ctg_slugs)
        url = base_url + "?" + parameters

        async with session.get(url) as response:
            return await response.json()

    async def crawl_all_pages_async(self, max_concurrent=10):

        all_raw_data = []

        async with aiohttp.ClientSession() as session:
            # 1. 첫페이지만 수집
            first_response = await self.fetch_page(session, 1)

            total_count = first_response.get('data', {}).get('totalCount', 0)
            total_pages = (total_count // 100) + (1 if total_count % 100 else 0)

            first_page_items = first_response.get('data', {}).get('items', [])
            all_raw_data.extend(first_page_items)

            # 2. 2페이지부터 끝페이지+1 수집
            remaining_pages = range(2, total_pages + 1)

            if not remaining_pages:
                return all_raw_data

            for i in range(0, len(remaining_pages), max_concurrent):
                batch_pages = remaining_pages[i:i + max_concurrent]

                tasks = [self.fetch_page(session, page) for page in batch_pages]

                responses = await asyncio.gather(*tasks)

                for response_data in responses:
                    lecture_items = response_data.get('data', {}).get('items', [])
                    all_raw_data.extend(lecture_items)

        return all_raw_data

    def filter_data(self, raw_lecture_items):

        filtered_data = []
        # id값으로 중복제거
        unique_ids = set()

        for item in raw_lecture_items:
            course = item.get('course', {})
            course_id = course.get('id')

            if not course_id or course_id in unique_ids:
                continue

            unique_ids.add(course_id)

            filtered_data.append(item)

        return filtered_data

    def convert_to_db_format(self, filtered_items):

        processed_data = []

        for item in filtered_items:
            course = item.get('course', {})
            instructor = item.get('instructor', {})
            metadata = course.get('metadata', {})
            list_price = item.get('listPrice', {})
            slug = course.get('slug')

        # 난이도 매핑
            level_map = {'BASIC': 'EASY', 'BEGINNER': 'EASY', 'INTERMEDIATE': 'NORMAL', 'ADVANCED': 'HARD'}
            api_level = metadata.get('level', 'BEGINNER')
            difficulty = level_map.get(api_level, 'EASY')

        # 시간 변환
            runtime_seconds = course.get('runtimeSecond', 0)
            duration_minutes = runtime_seconds // 60

            lecture_info = {
                'title': course.get('title', ''),
                'instructor': instructor.get('name', ''),
                'average_rating': round(course.get('star', 0.0), 2),
                'duration': duration_minutes,
                'difficulty': difficulty,
                'description': course.get('description', '강의 설명이 없습니다.'),
                'platform': 'INFLEARN',
                'original_price': list_price.get('regularPrice', 0),
                'discount_price': list_price.get('payPrice', 0),
                'url_link': f"https://www.inflearn.com/course/{slug}" if slug else '',
                'thumbnail_img_url': course.get('thumbnailUrl', ''),
                'categories_raw': metadata.get('parentCategories', []),
            }
            processed_data.append(lecture_info)

        return processed_data

    async def crawl_and_process(self, max_concurrent=10):
        raw_data = await self.crawl_all_pages_async(max_concurrent)
        filtered_data = self.filter_data(raw_data)
        db_data = self.convert_to_db_format(filtered_data)
        return db_data
