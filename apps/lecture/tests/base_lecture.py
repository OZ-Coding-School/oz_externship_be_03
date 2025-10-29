from rest_framework.test import APITestCase

from apps.lecture.models import (
    Category,
    CrawledLecture,
    LectureCategory,
)


class BaseLectureTest(APITestCase):
    def setUp(self) -> None:
        self.category1 = Category.objects.create(name="Python")
        self.category2 = Category.objects.create(name="C++")

        self.lecture1 = CrawledLecture.objects.create(
            title="Python 기초",
            instructor="홍길동",
            average_rating=4.5,
            duration=600,
            difficulty="EASY",
            description="Python 기초 강의",
            platform="INFLEARN",
            original_price=50000,
            discount_price=30000,
            url_link="https://www.inflearn.com/python",
        )
        LectureCategory.objects.create(lecture=self.lecture1, category=self.category1)

        self.lecture2 = CrawledLecture.objects.create(
            title="C++ 심화",
            instructor="김철수",
            average_rating=4.8,
            duration=180,
            difficulty="HARD",
            description="C++ 심화 강의",
            platform="INFLEARN",
            original_price=80000,
            discount_price=60000,
            url_link="https://inflearn.com/C",
        )
        LectureCategory.objects.create(lecture=self.lecture2, category=self.category2)
