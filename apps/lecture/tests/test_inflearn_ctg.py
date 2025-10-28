# apps/lecture/tests/test_inflearn_ctg.py
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.lecture.crawlers.inflearn_ctg import InflearnCategoryCrawler


class InflearnCategoryCrawlerTest(TestCase):
    """인프런 카테고리 크롤러 테스트"""

    def setUp(self) -> None:
        self.crawler = InflearnCategoryCrawler()

        # Mock 데이터를 setUp에서 한 번만 정의
        self.mock_response = {
            "statusCode": "200",
            "data": [
                {
                    "title": "개발",
                    "children": [
                        {
                            "title": "언어",
                            "skills": [
                                {"title": "Python"},
                                {"title": "Java"},
                                {"title": "Python"},  # 중복
                            ],
                        }
                    ],
                }
            ],
        }

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_success(self, mock_get_json: Mock) -> None:
        """기본 동작 테스트"""
        mock_get_json.return_value = self.mock_response

        result = self.crawler.crawl()

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # 첫 번째 항목만 검증
        item = result[0]
        self.assertIn("name", item)
        self.assertIsInstance(item["name"], str)

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_removes_duplicates(self, mock_get_json: Mock) -> None:
        """중복 제거 테스트"""
        mock_get_json.return_value = self.mock_response

        result = self.crawler.crawl()
        names = [c["name"] for c in result]

        self.assertEqual(len(names), len(set(names)))

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_sorts_results(self, mock_get_json: Mock) -> None:
        """정렬 테스트"""
        mock_get_json.return_value = self.mock_response

        result = self.crawler.crawl()
        names = [c["name"] for c in result]

        self.assertEqual(names, sorted(names))

    @patch("apps.lecture.crawlers.inflearn_ctg.logger")
    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_handles_none_response(self, mock_get_json: Mock, mock_logger: Mock) -> None:
        """None 응답 처리 테스트"""
        mock_get_json.return_value = None

        result = self.crawler.crawl()

        self.assertEqual(result, [])
        mock_logger.error.assert_called_once_with("카테고리 데이터를 가져올 수 없습니다")

    @patch("apps.lecture.crawlers.inflearn_ctg.logger")
    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_handles_error_status_code(self, mock_get_json: Mock, mock_logger: Mock) -> None:
        """에러 상태 코드 처리 테스트"""
        mock_get_json.return_value = {"statusCode": "500", "data": []}

        result = self.crawler.crawl()

        self.assertEqual(result, [])
        mock_logger.error.assert_called_once_with("카테고리 데이터를 가져올 수 없습니다")

    @patch("apps.lecture.crawlers.inflearn_ctg.logger")
    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_handles_missing_status_code(self, mock_get_json: Mock, mock_logger: Mock) -> None:
        """상태 코드 없는 응답 처리 테스트"""
        mock_get_json.return_value = {"data": [{"title": "Python"}]}

        result = self.crawler.crawl()

        self.assertEqual(result, [])
        mock_logger.error.assert_called_once_with("카테고리 데이터를 가져올 수 없습니다")

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_handles_empty_data(self, mock_get_json: Mock) -> None:
        """빈 데이터 처리 테스트"""
        mock_get_json.return_value = {"statusCode": "200", "data": []}

        result = self.crawler.crawl()

        self.assertEqual(result, [])
