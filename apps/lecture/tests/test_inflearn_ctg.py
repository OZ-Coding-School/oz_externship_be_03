from unittest.mock import Mock, patch

from django.test import TestCase

from apps.lecture.crawlers.inflearn_ctg import InflearnCategoryCrawler


class InflearnCategoryCrawlerTest(TestCase):
    """인프런 카테고리 크롤러 테스트"""

    def setUp(self) -> None:
        self.crawler = InflearnCategoryCrawler()

        self.mock_response = {
            "statusCode": "200",
            "data": [
                # 1. title/slug 누락으로 인한 continue 커버
                {"slug": "missing-parent-title"},
                {"title": "Missing Parent Slug"},
                # 2. valid_ctg_slugs에 없는 슬러그로 인한 continue 커버
                {"title": "Invalid Category", "slug": "invalid-slug"},
                {
                    "title": "개발·프로그래밍",
                    "slug": "it-programming",
                    "children": [
                        {
                            "title": "웹 개발",
                            "slug": "web-dev",
                            "skills": [
                                {"title": "Python", "slug": "python"},
                                {"title": "Java", "slug": "java"},
                                {"title": "Python", "slug": "python"},  # 중복 항목
                            ],
                        }
                    ],
                },
            ],
        }

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_success(self, mock_get_json: Mock) -> None:
        """기본 동작 테스트"""
        mock_get_json.return_value = self.mock_response

        result = self.crawler.crawl()

        # 총 유효 항목 4개 (불완전 항목 3개 + 중복 항목 1개는 필터링됨)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 4)

        item = result[0]
        self.assertIn("title", item)
        self.assertIn("slug", item)
        self.assertIsInstance(item["title"], str)
        self.assertIsInstance(item["slug"], str)

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_removes_duplicates(self, mock_get_json: Mock) -> None:
        """중복 제거 테스트"""
        mock_get_json.return_value = self.mock_response

        result = self.crawler.crawl()
        tuples = [(c["title"], c["slug"]) for c in result]

        self.assertEqual(len(tuples), len(set(tuples)))

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_sorts_results(self, mock_get_json: Mock) -> None:
        """정렬 테스트"""
        mock_get_json.return_value = self.mock_response

        result = self.crawler.crawl()
        titles = [c["title"] for c in result]

        self.assertEqual(titles, sorted(titles))

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
        mock_get_json.return_value = {"data": [{"title": "Python", "slug": "python"}]}

        result = self.crawler.crawl()

        self.assertEqual(result, [])
        mock_logger.error.assert_called_once_with("카테고리 데이터를 가져올 수 없습니다")

    @patch("apps.lecture.crawlers.base_crawler.BaseCrawler.get_json")
    def test_crawl_handles_empty_data(self, mock_get_json: Mock) -> None:
        """빈 데이터 처리 테스트"""
        mock_get_json.return_value = {"statusCode": "200", "data": []}

        result = self.crawler.crawl()

        self.assertEqual(result, [])
