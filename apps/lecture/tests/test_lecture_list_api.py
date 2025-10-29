from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.lecture.models import (
    Category,
    CrawledLecture,
    CrawledLectureReview,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
)

User = get_user_model()


class LectureListApiViewTest(APITestCase):
    def setUp(self) -> None:
        self.list_url = reverse("lecture-list")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testtest123!",
            nickname="테스트유저",
            name="테스터",
            phone_number="010-1234-5678",
            birthday=date(1990, 1, 1),
            gender="MALE",
        )

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

    def test_lecture_list(self) -> None:
        """강의 목록 조회 성공"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

    def test_lecture_list_with_bookmark(self) -> None:
        """북마크 확인"""
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]
        lecture1_data = next((l for l in results if l["title"] == "Python 기초"), None)

        self.assertIsNotNone(lecture1_data)
        assert lecture1_data is not None
        self.assertTrue(lecture1_data["is_bookmarked"])

    def test_search_by_title(self) -> None:
        """검색기능 테스트"""
        response = self.client.get(self.list_url, {"search": "Python"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Python 기초")

    def test_filter_by_category(self) -> None:
        """카테고리 필터링"""
        response = self.client.get(self.list_url, {"category": "C++"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "C++ 심화")

    def test_ordering_by_rating(self) -> None:
        """평점 내림차순 정렬"""
        response = self.client.get(self.list_url, {"ordering": "-rating"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["average_rating"], "4.80")

    def test_empty_result(self) -> None:
        """검색 결과 없음"""
        response = self.client.get(self.list_url, {"search": "FastAPI 종결"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_search_log_created(self) -> None:
        """검색 로그 저장"""
        self.client.force_authenticate(user=self.user)
        log_count = LectureSearchLog.objects.count()

        self.client.get(self.list_url, {"search": "Python"})

        self.assertEqual(LectureSearchLog.objects.count(), log_count + 1)
        log = LectureSearchLog.objects.all()[0]
        self.assertEqual(log.keyword, "Python")


class LectureReviewListApiViewTest(APITestCase):
    def setUp(self) -> None:
        self.category = Category.objects.create(name="Python")

        self.lecture = CrawledLecture.objects.create(
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
        LectureCategory.objects.create(lecture=self.lecture, category=self.category)

        self.review1 = CrawledLectureReview.objects.create(
            lecture=self.lecture,
            rating="5_OUT_OF_5_STARS",
            content="최고의 강의",
        )
        self.review2 = CrawledLectureReview.objects.create(
            lecture=self.lecture,
            rating="1_OUT_OF_5_STARS",
            content="최악의 강의",
        )
        self.review3 = CrawledLectureReview.objects.create(
            lecture=self.lecture,
            rating="3_OUT_OF_5_STARS",
            content="평범한 강의",
        )
        self.review4 = CrawledLectureReview.objects.create(
            lecture=self.lecture,
            rating="2_OUT_OF_5_STARS",
            content="나쁜 강의",
        )
        self.review5 = CrawledLectureReview.objects.create(
            lecture=self.lecture,
            rating="4_OUT_OF_5_STARS",
            content="좋은 강의",
        )

        self.review_url = reverse("lecture-review-list", kwargs={"uuid": self.lecture.uuid})

    def test_lecture_review_list(self) -> None:
        """강의 리뷰 조회 확인 (최신4개)"""
        response = self.client.get(self.review_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

        review_ids = [review["id"] for review in response.data]
        self.assertNotIn(self.review1.id, review_ids)
        self.assertIn(self.review5.id, review_ids)

    def test_lecture_review_list_nonexistent_uuid(self) -> None:
        """존재하지않은 uuid"""
        nonexistent_url = reverse("lecture-review-list", kwargs={"uuid": "00000000-0000-0000-0000-000000000000"})
        response = self.client.get(nonexistent_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "lecture_not_found")
