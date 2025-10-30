from rest_framework.test import APITestCase

from apps.lecture.models import (
    Category,
    CrawledLecture,
    LectureCategory,
)


class BaseLectureTest(APITestCase):
    category1: Category
    category2: Category
    lecture1: CrawledLecture
    lecture2: CrawledLecture

    @classmethod
    def setUpTestData(cls) -> None:
        cls.category1, cls.category2 = Category.objects.bulk_create(
            [
                Category(name="Python"),
                Category(name="C++"),
            ]
        )

        cls.lecture1, cls.lecture2 = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
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
                ),
                CrawledLecture(
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
                ),
            ]
        )

        LectureCategory.objects.bulk_create(
            [
                LectureCategory(lecture=cls.lecture1, category=cls.category1),
                LectureCategory(lecture=cls.lecture2, category=cls.category2),
            ]
        )
