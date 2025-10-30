import datetime
from typing import Any, List

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.users.models import User


class LectureBookmarkAPITestCase(TestCase):
    """강의 북마크 API 통합 테스트"""

    user1: User
    user2: User
    lecture1: CrawledLecture
    lecture2: CrawledLecture
    lecture3: CrawledLecture
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트 데이터 설정 (클래스 레벨에서 한 번만 실행)"""
        # 테스트 유저 bulk_create
        cls.user1, cls.user2 = User.objects.bulk_create(
            [
                User(
                    email="test1@example.com",
                    nickname="testuser1",
                    name="테스트유저1",
                    phone_number="010-1234-5678",
                    birthday=datetime.date(1990, 1, 1),
                    gender="MALE",
                    is_active=True,
                ),
                User(
                    email="test2@example.com",
                    nickname="testuser2",
                    name="테스트유저2",
                    phone_number="010-8765-4321",
                    birthday=datetime.date(1995, 5, 15),
                    gender="FEMALE",
                    is_active=True,
                ),
            ]
        )
        # 비밀번호는 bulk_create 후 별도 설정
        cls.user1.set_password("testpass123")
        cls.user1.save()
        cls.user2.set_password("testpass123")
        cls.user2.save()

        # 테스트 강의 bulk_create
        cls.lecture1, cls.lecture2, cls.lecture3 = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title="Python 기초 강의",
                    instructor="김강사",
                    thumbnail_img_url="https://example.com/thumb1.jpg",
                    platform="INFLEARN",
                    difficulty="EASY",
                    original_price=50000,
                    discount_price=40000,
                    duration=120,
                    url_link="https://example.com/course/1",
                    description="파이썬 기초 강의입니다.",
                    average_rating=4.5,
                ),
                CrawledLecture(
                    title="Django 심화 강의",
                    instructor="이강사",
                    thumbnail_img_url="https://example.com/thumb2.jpg",
                    platform="UDEMY",
                    difficulty="HARD",
                    original_price=80000,
                    discount_price=60000,
                    duration=300,
                    url_link="https://example.com/course/2",
                    description="Django 심화 강의입니다.",
                    average_rating=4.8,
                ),
                CrawledLecture(
                    title="React 입문",
                    instructor="박강사",
                    thumbnail_img_url="https://example.com/thumb3.jpg",
                    platform="INFLEARN",
                    difficulty="NORMAL",
                    original_price=60000,
                    discount_price=50000,
                    duration=180,
                    url_link="https://example.com/course/3",
                    description="React 입문 강의입니다.",
                    average_rating=4.3,
                ),
            ]
        )

    def setUp(self) -> None:
        """각 테스트 메서드 실행 전 설정"""
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

    def tearDown(self) -> None:
        """각 테스트 메서드 실행 후 정리"""
        LectureBookmark.objects.all().delete()


class BookmarkListTests(LectureBookmarkAPITestCase):
    """북마크 목록 조회 테스트"""

    def test_get_empty_bookmark_list(self) -> None:
        """빈 북마크 목록 조회"""
        response: Response = self.client.get(reverse("bookmark-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "북마크 강의 목록 조회가 완료되었습니다.")
        self.assertEqual(response.data["data"]["count"], 0)
        self.assertEqual(len(response.data["data"]["results"]), 0)

    def test_get_bookmark_list_with_data(self) -> None:
        """북마크가 있는 경우 목록 조회"""
        # 북마크 bulk_create
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user1, lecture=self.lecture1),
                LectureBookmark(user=self.user1, lecture=self.lecture2),
            ]
        )

        response: Response = self.client.get(reverse("bookmark-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 2)
        self.assertEqual(len(response.data["data"]["results"]), 2)

        # 최신순 정렬 확인 (created_at 기준 내림차순)
        results: list[dict[str, Any]] = response.data["data"]["results"]
        self.assertEqual(results[0]["lecture_info"]["title"], "Django 심화 강의")
        self.assertEqual(results[1]["lecture_info"]["title"], "Python 기초 강의")

    def test_bookmark_list_search_by_title(self) -> None:
        """강의명으로 검색"""
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user1, lecture=self.lecture1),
                LectureBookmark(user=self.user1, lecture=self.lecture2),
                LectureBookmark(user=self.user1, lecture=self.lecture3),
            ]
        )

        response: Response = self.client.get(reverse("bookmark-list-create") + "?search=Python")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["lecture_info"]["title"], "Python 기초 강의")

    def test_bookmark_list_search_by_instructor(self) -> None:
        """강사명으로 검색"""
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user1, lecture=self.lecture1),
                LectureBookmark(user=self.user1, lecture=self.lecture2),
            ]
        )

        response: Response = self.client.get(reverse("bookmark-list-create") + "?search=이강사")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["lecture_info"]["instructor"], "이강사")

    def test_bookmark_list_pagination(self) -> None:
        """페이지네이션 테스트"""
        # 15개의 강의 bulk_create
        lectures: List[CrawledLecture] = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title=f"테스트 강의 {i}",
                    instructor=f"강사 {i}",
                    platform="INFLEARN",
                    difficulty="NORMAL",
                    original_price=50000,
                    discount_price=40000,
                    duration=120,
                    url_link=f"https://example.com/course/{i}",
                    description=f"테스트 강의 {i}입니다.",
                )
                for i in range(15)
            ]
        )

        # 북마크 bulk_create
        LectureBookmark.objects.bulk_create([LectureBookmark(user=self.user1, lecture=lecture) for lecture in lectures])

        # 첫 페이지 조회 (기본 10개)
        response: Response = self.client.get(reverse("bookmark-list-create") + "?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 10)
        self.assertIsNotNone(response.data["data"]["next"])
        self.assertIsNone(response.data["data"]["previous"])

        # 두 번째 페이지 조회
        response = self.client.get(reverse("bookmark-list-create") + "?page=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 5)
        self.assertIsNone(response.data["data"]["next"])
        self.assertIsNotNone(response.data["data"]["previous"])

    def test_bookmark_list_custom_page_size(self) -> None:
        """커스텀 페이지 크기 테스트"""
        # 25개의 강의 bulk_create
        lectures: List[CrawledLecture] = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title=f"테스트 강의 {i}",
                    instructor=f"강사 {i}",
                    platform="INFLEARN",
                    difficulty="NORMAL",
                    original_price=50000,
                    discount_price=40000,
                    duration=120,
                    url_link=f"https://example.com/course/{i}",
                    description=f"테스트 강의 {i}입니다.",
                )
                for i in range(25)
            ]
        )

        # 북마크 bulk_create
        LectureBookmark.objects.bulk_create([LectureBookmark(user=self.user1, lecture=lecture) for lecture in lectures])

        response: Response = self.client.get(reverse("bookmark-list-create") + "?page_size=20")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 20)

    def test_bookmark_list_user_isolation(self) -> None:
        """사용자별 북마크 격리 테스트"""
        # 각 유저의 북마크 bulk_create
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user1, lecture=self.lecture1),
                LectureBookmark(user=self.user2, lecture=self.lecture2),
            ]
        )

        # user1로 조회
        response: Response = self.client.get(reverse("bookmark-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["lecture_info"]["title"], "Python 기초 강의")

    def test_bookmark_list_unauthorized(self) -> None:
        """인증되지 않은 사용자의 접근 테스트"""
        self.client.force_authenticate(user=None)
        response: Response = self.client.get(reverse("bookmark-list-create"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BookmarkCreateTests(LectureBookmarkAPITestCase):
    """북마크 추가 테스트"""

    def test_create_bookmark_success(self) -> None:
        """북마크 추가 성공"""
        data: dict[str, Any] = {"lecture_id": self.lecture1.id}
        response: Response = self.client.post(reverse("bookmark-list-create"), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "북마크가 추가되었습니다.")

        # DB에 실제로 생성되었는지 확인
        self.assertTrue(LectureBookmark.objects.filter(user=self.user1, lecture=self.lecture1).exists())

    def test_create_duplicate_bookmark(self) -> None:
        """중복 북마크 추가 시도"""
        # 첫 번째 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        # 중복 생성 시도
        data: dict[str, Any] = {"lecture_id": self.lecture1.id}
        response: Response = self.client.post(reverse("bookmark-list-create"), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 북마크한 강의입니다", str(response.data))

    def test_create_bookmark_invalid_lecture_id(self) -> None:
        """존재하지 않는 강의 ID로 북마크 추가 시도"""
        data: dict[str, Any] = {"lecture_id": 99999}
        response: Response = self.client.post(reverse("bookmark-list-create"), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_bookmark_missing_lecture_id(self) -> None:
        """lecture_id 누락"""
        data: dict[str, Any] = {}
        response: Response = self.client.post(reverse("bookmark-list-create"), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_bookmark_unauthorized(self) -> None:
        """인증되지 않은 사용자의 북마크 추가 시도"""
        self.client.force_authenticate(user=None)
        data: dict[str, Any] = {"lecture_id": self.lecture1.id}
        response: Response = self.client.post(reverse("bookmark-list-create"), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BookmarkDeleteTests(LectureBookmarkAPITestCase):
    """북마크 삭제 테스트"""

    def test_delete_bookmark_success(self) -> None:
        """북마크 삭제 성공"""
        # 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        response: Response = self.client.delete(reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id}))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.data["detail"], "북마크가 삭제되었습니다.")

        # DB에서 실제로 삭제되었는지 확인
        self.assertFalse(LectureBookmark.objects.filter(user=self.user1, lecture=self.lecture1).exists())

    def test_delete_nonexistent_bookmark(self) -> None:
        """존재하지 않는 북마크 삭제 시도"""
        response: Response = self.client.delete(reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "존재하지 않는 북마크입니다.")

    def test_delete_other_user_bookmark(self) -> None:
        """다른 사용자의 북마크 삭제 시도"""
        # user2의 북마크 생성
        LectureBookmark.objects.create(user=self.user2, lecture=self.lecture1)

        # user1로 삭제 시도
        response: Response = self.client.delete(reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # user2의 북마크는 여전히 존재해야 함
        self.assertTrue(LectureBookmark.objects.filter(user=self.user2, lecture=self.lecture1).exists())

    def test_delete_bookmark_unauthorized(self) -> None:
        """인증되지 않은 사용자의 북마크 삭제 시도"""
        # 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        self.client.force_authenticate(user=None)
        response: Response = self.client.delete(reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id}))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BookmarkIntegrationTests(LectureBookmarkAPITestCase):
    """북마크 API 통합 시나리오 테스트"""

    def test_full_bookmark_workflow(self) -> None:
        """전체 북마크 워크플로우 테스트: 추가 -> 조회 -> 삭제"""
        # 1. 북마크 추가
        data: dict[str, Any] = {"lecture_id": self.lecture1.id}
        response: Response = self.client.post(reverse("bookmark-list-create"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 2. 북마크 목록 조회
        response = self.client.get(reverse("bookmark-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["lecture_info"]["title"], "Python 기초 강의")

        # 3. 북마크 삭제
        response = self.client.delete(reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 4. 삭제 후 목록 조회
        response = self.client.get(reverse("bookmark-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 0)

    def test_search_with_pagination(self) -> None:
        """검색과 페이지네이션 조합 테스트"""
        # Python 관련 강의 15개 bulk_create
        python_lectures: List[CrawledLecture] = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title=f"Python 강의 {i}",
                    instructor=f"강사 {i}",
                    platform="INFLEARN",
                    difficulty="NORMAL",
                    original_price=50000,
                    discount_price=40000,
                    duration=120,
                    url_link=f"https://example.com/course/{i}",
                    description=f"Python 강의 {i}입니다.",
                )
                for i in range(15)
            ]
        )

        # Django 강의 5개 bulk_create
        django_lectures: List[CrawledLecture] = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title=f"Django 강의 {i}",
                    instructor=f"강사 {i}",
                    platform="INFLEARN",
                    difficulty="NORMAL",
                    original_price=50000,
                    discount_price=40000,
                    duration=120,
                    url_link=f"https://example.com/course/django-{i}",
                    description=f"Django 강의 {i}입니다.",
                )
                for i in range(5)
            ]
        )

        # 북마크 bulk_create
        LectureBookmark.objects.bulk_create(
            [LectureBookmark(user=self.user1, lecture=lecture) for lecture in python_lectures + django_lectures]
        )

        # Python 검색 - 첫 페이지
        response: Response = self.client.get(reverse("bookmark-list-create") + "?search=Python&page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 15)
        self.assertEqual(len(response.data["data"]["results"]), 10)

        # Python 검색 - 두 번째 페이지
        response = self.client.get(reverse("bookmark-list-create") + "?search=Python&page=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 5)
