import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import requests

# 프로그램이 실행되는 동안 익셉트 발생시 에러기록 (콘솔에기록<터미널/화면>)
logger = logging.getLogger(__name__)

# 크롤링 장비 준비
class BaseCrawler(ABC):
    def __init__(self, base_url: str, auth_cookie: Optional[str] = None) -> None:
        self.base_url = base_url
        self.session = requests.Session()
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
            logger.info(f"API 주소 요청: {url}")
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
        # 3단계 안전장치 
        # - 1단계 - response 자체가 없는 경우
        if not response:
            return None
        try:
            return response.json()
        # - 2단계 - 응답은 왔는데 JSON 형식이 아니거나 깨진 경우
        except ValueError as e:  
            logger.error(f"JSON 파싱 실패: {e}")
            return None
        # - 3단계 - 최후의 안전망
        except Exception as e:  # 기타 예외
            logger.error(f"응답 처리 중 오류 발생: {e}")
            return None

    def close(self) -> None:
        self.session.close()

    # 파생 크롤러가 반드시 구현 자유롭게
    @abstractmethod
    def crawl(self, *args: Any, **kwargs: Any) -> Any:
        pass
