from __future__ import annotations

from datetime import date
from typing import Any, List

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.tests.base_lecture import BaseLectureTest

User = get_user_model()


class LectureBookmarkIntegrationTest(BaseLectureTest):
    """북마크 기능 통합 테스트"""

    client: APIClient
    user: Any
    user2: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            nickname="testuser",
            name="테스트유저",
            phone_number="010-1234-5678",
            birthday=date(1990, 1, 1),
            gender="MALE",
        )

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_bookmark_create_and_list(self) -> None:
        """북마크 생성 및 목록 조회"""
        url: str = reverse("bookmark-list-create")
        response: Response = self.client.post(
            url,
            {"lecture_id": self.lecture1.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "북마크가 추가되었습니다.")
        self.assertTrue(LectureBookmark.objects.filter(user=self.user, lecture=self.lecture1).exists())

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertIn("results", response.data["data"])
        self.assertEqual(len(response.data["data"]["results"]), 1)
        self.assertEqual(
            response.data["data"]["results"][0]["lecture_info"]["title"],
            "Python 기초",
        )

    def test_bookmark_duplicate_prevention(self) -> None:
        """중복 북마크 방지"""
        url: str = reverse("bookmark-list-create")
        self.client.post(url, {"lecture_id": self.lecture1.id}, format="json")

        response: Response = self.client.post(url, {"lecture_id": self.lecture1.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "이미 북마크한 강의입니다.")
        self.assertEqual(LectureBookmark.objects.filter(user=self.user, lecture=self.lecture1).count(), 1)

    def test_bookmark_integrity_error(self) -> None:
        """DB 레벨 중복 제약 조건"""
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        with self.assertRaises(IntegrityError):
            LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

    def test_bookmark_delete(self) -> None:
        """북마크 삭제"""
        LectureBookmark.objects.bulk_create([LectureBookmark(user=self.user, lecture=self.lecture1)])

        url: str = reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id})
        response: Response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LectureBookmark.objects.filter(user=self.user, lecture=self.lecture1).exists())

    def test_bookmark_delete_nonexistent(self) -> None:
        """존재하지 않는 북마크 삭제 시도"""
        url: str = reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id})
        response: Response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "존재하지 않는 북마크입니다.")

    def test_bookmark_search_by_title(self) -> None:
        """강의 제목으로 북마크 검색"""
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user, lecture=self.lecture1),
                LectureBookmark(user=self.user, lecture=self.lecture2),
            ]
        )

        url: str = reverse("bookmark-list-create")
        response: Response = self.client.get(url, {"search": "Python"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 1)
        self.assertEqual(response.data["data"]["results"][0]["lecture_info"]["title"], "Python 기초")

    def test_bookmark_search_by_instructor(self) -> None:
        """강사명으로 북마크 검색"""
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user, lecture=self.lecture1),
                LectureBookmark(user=self.user, lecture=self.lecture2),
            ]
        )

        url: str = reverse("bookmark-list-create")
        response: Response = self.client.get(url, {"search": "김철수"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 1)
        self.assertEqual(response.data["data"]["results"][0]["lecture_info"]["instructor"], "김철수")

    def test_bookmark_pagination(self) -> None:
        """북마크 페이지네이션"""
        lectures: List[CrawledLecture] = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title=f"강의 {i}",
                    instructor="강사",
                    average_rating=4.0,
                    duration=100,
                    difficulty="EASY",
                    description="설명",
                    platform="INFLEARN",
                    original_price=10000,
                    discount_price=5000,
                    url_link=f"https://example.com/{i}",
                )
                for i in range(11)
            ]
        )

        LectureBookmark.objects.bulk_create([LectureBookmark(user=self.user, lecture=lecture) for lecture in lectures])

        url: str = reverse("bookmark-list-create")
        response: Response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 10)
        self.assertIsNotNone(response.data["data"]["next"])

        response = self.client.get(url, {"page": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["results"]), 1)

    def test_bookmark_invalid_lecture_id(self) -> None:
        """존재하지 않는 강의 ID로 북마크 생성 시도"""
        url: str = reverse("bookmark-list-create")
        response: Response = self.client.post(url, {"lecture_id": 99999}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lecture_id", response.data)

    def test_bookmark_missing_lecture_id(self) -> None:
        """lecture_id 누락 시 검증 실패"""
        url: str = reverse("bookmark-list-create")
        response: Response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lecture_id", response.data)

    def test_bookmark_authentication_required(self) -> None:
        """인증되지 않은 사용자의 접근 차단"""
        self.client.force_authenticate(user=None)

        list_url: str = reverse("bookmark-list-create")
        delete_url: str = reverse("bookmark-delete", kwargs={"lecture_id": self.lecture1.id})

        response: Response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(list_url, {"lecture_id": self.lecture1.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
