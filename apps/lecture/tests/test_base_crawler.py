# apps/lecture/tests/test_base_crawler.py
from typing import Any, Dict
from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from apps.lecture.crawlers.base_crawler import BaseCrawler


# 테스트용 구체 클래스 (ABC라서 직접 인스턴스 못 만듦)
class TestCrawler(BaseCrawler):
    """테스트용 크롤러"""

    def crawl(self, *args: Any, **kwargs: Any) -> Dict[str, str]:
        """추상 메서드 구현"""
        return {"test": "data"}


class BaseCrawlerTest(TestCase):
    """베이스 크롤러 테스트"""

    def setUp(self) -> None:
        self.crawler = TestCrawler(base_url="https://api.example.com")
        self.crawler_with_auth = TestCrawler(base_url="https://api.example.com", auth_cookie="session_id=abc123")

    def test_init_without_auth(self) -> None:
        """인증 없이 초기화 테스트"""
        self.assertEqual(self.crawler.base_url, "https://api.example.com")
        self.assertIn("User-Agent", self.crawler.headers)
        self.assertNotIn("Cookie", self.crawler.headers)

    def test_init_with_auth(self) -> None:
        """인증 쿠키와 함께 초기화 테스트"""
        self.assertEqual(self.crawler_with_auth.base_url, "https://api.example.com")
        self.assertIn("Cookie", self.crawler_with_auth.headers)
        self.assertEqual(self.crawler_with_auth.headers["Cookie"], "session_id=abc123")

    @patch("apps.lecture.crawlers.base_crawler.time.sleep")
    @patch("apps.lecture.crawlers.base_crawler.requests.Session.get")
    def test_make_request_success(self, mock_get: Mock, mock_sleep: Mock) -> None:
        """정상 요청 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 요청 실행
        response = self.crawler._make_request("https://api.example.com/test")

        # 검증
        self.assertIsNotNone(response)
        if response is not None:  # Type narrowing
            self.assertEqual(response.status_code, 200)
        mock_get.assert_called_once()
        mock_sleep.assert_called_once_with(3)

    @patch("apps.lecture.crawlers.base_crawler.logger")
    @patch("apps.lecture.crawlers.base_crawler.requests.Session.get")
    def test_make_request_http_error(self, mock_get: Mock, mock_logger: Mock) -> None:
        """HTTP 에러 처리 테스트"""
        # Mock 에러 설정
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")

        # 요청 실행
        response = self.crawler._make_request("https://api.example.com/test")

        # 검증
        self.assertIsNone(response)
        mock_logger.error.assert_called_once()

    @patch("apps.lecture.crawlers.base_crawler.logger")
    @patch("apps.lecture.crawlers.base_crawler.requests.Session.get")
    def test_make_request_timeout(self, mock_get: Mock, mock_logger: Mock) -> None:
        """타임아웃 처리 테스트"""
        # Mock 타임아웃 설정
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        # 요청 실행
        response = self.crawler._make_request("https://api.example.com/test")

        # 검증
        self.assertIsNone(response)
        mock_logger.error.assert_called_once()

    @patch("apps.lecture.crawlers.base_crawler.logger")
    @patch("apps.lecture.crawlers.base_crawler.requests.Session.get")
    def test_make_request_connection_error(self, mock_get: Mock, mock_logger: Mock) -> None:
        """연결 에러 처리 테스트"""
        # Mock 연결 에러 설정
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        # 요청 실행
        response = self.crawler._make_request("https://api.example.com/test")

        # 검증
        self.assertIsNone(response)
        mock_logger.error.assert_called_once()

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler._make_request")
    def test_get_json_success(self, mock_make_request: Mock) -> None:
        """JSON 파싱 성공 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok", "data": [1, 2, 3]}
        mock_make_request.return_value = mock_response

        # 요청 실행
        result = self.crawler.get_json("https://api.example.com/test")

        # 검증
        self.assertIsNotNone(result)
        if result is not None:  # Type narrowing
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["data"], [1, 2, 3])

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler._make_request")
    def test_get_json_none_response(self, mock_make_request: Mock) -> None:
        """None 응답 처리 테스트"""
        mock_make_request.return_value = None

        result = self.crawler.get_json("https://api.example.com/test")

        self.assertIsNone(result)

    @patch("apps.lecture.crawlers.base_crawler.logger")
    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler._make_request")
    def test_get_json_parse_error(self, mock_make_request: Mock, mock_logger: Mock) -> None:
        """JSON 파싱 에러 테스트"""
        # Mock 응답 설정 (JSON 파싱 실패)
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_make_request.return_value = mock_response

        # 요청 실행
        result = self.crawler.get_json("https://api.example.com/test")

        # 검증
        self.assertIsNone(result)
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        self.assertIn("JSON 파싱 실패", call_args)

    @patch("apps.lecture.crawlers.base_crawler.logger")
    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler._make_request")
    def test_get_json_unexpected_error(self, mock_make_request: Mock, mock_logger: Mock) -> None:
        """예상치 못한 에러 처리 테스트"""
        # Mock 응답 설정 (예상치 못한 에러)
        mock_response = Mock()
        mock_response.json.side_effect = Exception("Unexpected error")
        mock_make_request.return_value = mock_response

        # 요청 실행
        result = self.crawler.get_json("https://api.example.com/test")

        # 검증
        self.assertIsNone(result)
        self.assertEqual(mock_logger.error.call_count, 1)
        call_args = mock_logger.error.call_args[0][0]
        self.assertIn("응답 처리 중 오류 발생", call_args)

    def test_close(self) -> None:
        """세션 종료 테스트"""
        with patch.object(self.crawler.session, "close") as mock_close:
            self.crawler.close()
            mock_close.assert_called_once()

    def test_crawl_abstract_method(self) -> None:
        """crawl 메서드 구현 확인"""
        result = self.crawler.crawl()
        self.assertEqual(result, {"test": "data"})
