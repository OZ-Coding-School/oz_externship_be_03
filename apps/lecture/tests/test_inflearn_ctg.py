from unittest import TestCase

from apps.lecture.crawlers.inflearn_ctg import InflearnCategoryCrawler


class InflearnCategoryCrawlerTest(TestCase):

    def setUp(self) -> None:
        self.crawler = InflearnCategoryCrawler()

    def test_crawl_success(self) -> None:
        """기본 동작 및 데이터 형식 테스트"""
        result = self.crawler.crawl()

        # 리스트 반환
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # ⭐ 올바른 데이터 형식 보장
        for item in result:
            # 1. 딕셔너리여야 함 {}
            self.assertIsInstance(item, dict, "각 항목은 딕셔너리여야 함")

            # 2. "name" 키가 있어야 함
            self.assertIn("name", item, '"name" 키가 있어야 함')

            # 3. "name" 값이 문자열이어야 함
            self.assertIsInstance(item["name"], str, '"name" 값은 문자열이어야 함')

            # 4. 비어있지 않아야 함
            self.assertGreater(len(item["name"]), 0, '"name" 값은 비어있으면 안됨')

            # 5. "name" 키만 있어야 함 (다른 키 없음)
            self.assertEqual(len(item.keys()), 1, '"name" 키만 있어야 함')

    def test_crawl_removes_duplicates(self) -> None:
        """중복 제거 테스트"""
        result = self.crawler.crawl()
        names = [c["name"] for c in result]
        self.assertEqual(len(names), len(set(names)))

    def test_crawl_sorts_results(self) -> None:
        """정렬 테스트"""
        result = self.crawler.crawl()
        names = [c["name"] for c in result]
        self.assertEqual(names, sorted(names))
