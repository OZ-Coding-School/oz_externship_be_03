from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from .base_lecture import BaseLectureTest

User = get_user_model()


class BaseAdminLectureTest(BaseLectureTest):
    admin_user: Any
    normal_user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.admin_user = User.objects.create_user(
            email="test1@example.com",
            password="testtest123!",
            nickname="테스트스태프",
            name="테스터",
            phone_number="010-1234-5678",
            birthday=date(1990, 1, 1),
            gender="MALE",
            is_staff=True,
        )

        cls.normal_user = User.objects.create_user(
            email="test2@example.com",
            password="testtest123!",
            nickname="테스트유저",
            name="테스터",
            phone_number="010-1234-5679",
            birthday=date(1990, 1, 1),
            gender="MALE",
        )


class AdminLectureAPITestCase(BaseAdminLectureTest):
    admin_lecture_list_url: str

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.admin_lecture_list_url = reverse("admin_lecture:admin-lecture-list")

    def test_admin_lecture_list(self) -> None:
        """스태프 및 관리자 목록 조회 성공"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.admin_lecture_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_failed_with_normal_user(self) -> None:
        """일반 사용자의 경우 실패 (403)"""
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.admin_lecture_list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_failed_without_authentication(self) -> None:
        """비로그인의 경우 실패 (401)"""
        response = self.client.get(self.admin_lecture_list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminLectureDetailApiViewTest(BaseAdminLectureTest):
    detail_url: str

    def test_admin_lecture_detail(self) -> None:
        """스태프 및 관리자 상세 조회 성공"""
        self.detail_url = reverse("admin_lecture:admin-lecture-detail", kwargs={"lecture_id": self.lecture1.id})
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_detail_not_found(self) -> None:
        """존재하지 않는 강의 조회 시도 (404)"""
        self.detail_url = reverse("admin_lecture:admin-lecture-detail", kwargs={"lecture_id": 51})
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
