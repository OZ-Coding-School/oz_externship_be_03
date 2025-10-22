import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

# 프로그램이 실행되는 동안 익셉트 발생시 에러기록 (콘솔에기록<터미널/화면>)
logger = logging.getLogger(__name__)


# 크롤링 장비 준비
class BaseCrawler(ABC):

    def __init__(self, base_url: str, auth_cookie: Optional[str] = None) -> None:
        self.base_url = base_url
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Chrome/120.0.6099.71 (Windows NT 10.0; Win64; x64)",
    self.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/128.0.0.0 Safari/537.36"
    }
        if auth_cookie:
            self.headers["Cookie"] = auth_cookie

    # 핵심: HTTP 요청
    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
        try:
            logger.info(f"API 주소 / 일반 HTML 주소 요청: {url}")
            response = self.session.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()  # 응답이 왔지만, 응답의 내용이 오류 메시지라면 응답으로 취급하지 않겠다 4xx 5xx
            time.sleep(3)
            return response
        except Exception as e:
            logger.error(f"요청 실패입니다: {e}")
            return None

    # 편의: API 호출
    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        response = self._make_request(url, params)
        return response.json() if response else None

    # 편의: HTML 크롤링
    def get_html(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[BeautifulSoup]:
        response = self._make_request(url, params)
        return BeautifulSoup(response.text, "html.parser") if response else None

    # 편의: HTML 파싱
    def safe_extract(
        self, soup: BeautifulSoup, selector: str, attribute: Optional[str] = None, default: Any = None
    ) -> Any:
        element = soup.select_one(selector)
        if not element:
            return default
        return element.get(attribute, default) if attribute else element.text.strip()

    def close(self) -> None:
        self.session.close()

    # 파생 크롤러가 반드시 구현 자유롭게
    @abstractmethod
    def crawl(self, *args: Any, **kwargs: Any) -> Any:
        pass
