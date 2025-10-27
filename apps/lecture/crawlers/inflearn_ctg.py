import logging
from typing import Dict, List

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class InflearnCategoryCrawler(BaseCrawler):

    def __init__(self) -> None:
        super().__init__(base_url="https://ucc-api.inflearn.com")

    def crawl(self) -> List[Dict[str, str]]:
        # API 호출
        url = f"{self.base_url}/client/api/v1/course-category"
        params = {"lang": "ko"}
        response = self.get_json(url, params)

        # 응답 검증 (None 체크 → 상태코드 체크)
        if not response or response.get("statusCode") not in ["200", 200, "OK"]:
            logger.error("카테고리 데이터를 가져올 수 없습니다")
            return []

        # 검증된 데이터 추출 (계층 구조)
        data = response.get("data", [])

        # ========== 데이터 가공 시작 ==========
        # 중복 제거를 위한 set 준비
        ctg_set: set[str] = set()

        # 계층 구조를 순회하며 평평하게 변환
        for item in data:
            if item.get("title"):
                ctg_set.add(item["title"].strip())

            for child in item.get("children", []):
                if child.get("title"):
                    ctg_set.add(child["title"].strip())

                for skill in child.get("skills", []):
                    if skill.get("title"):
                        ctg_set.add(skill["title"].strip())

        # 정렬 후 딕셔너리 리스트로 변환 (DB/API 저장 형식)
        ctg = [{"name": name} for name in sorted(ctg_set)]
        # ====================================

        logger.info(f"총 {len(ctg)}개 카테고리 수집 완료")
        return ctg
