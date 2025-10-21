import logging
from typing import Any, Dict, List

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class InflearnCategoryCrawler(BaseCrawler):

    def __init__(self) -> None:
        super().__init__(base_url="https://ucc-api.inflearn.com")

    def crawl(self) -> List[Dict[str, str]]:
        url = f"{self.base_url}/client/api/v1/course-category"
        params = {"lang": "ko"}

        response = self.get_json(url, params)

        if not response or response.get("statusCode") != "OK":
            logger.error("카테고리 데이터를 가져올 수 없습니다")
            return []

        data = response.get("data", [])

        ctg_set: set[str] = set()

        for item in data:
            if item.get("title"):
                ctg_set.add(item["title"].strip())

            for child in item.get("children", []):
                if child.get("title"):
                    ctg_set.add(child["title"].strip())

                for skill in child.get("skills", []):
                    if skill.get("title"):
                        ctg_set.add(skill["title"].strip())

        ctg = [{"name": name} for name in sorted(ctg_set)]

        logger.info(f"총 {len(ctg)}개 카테고리 수집 완료")
        return ctg
