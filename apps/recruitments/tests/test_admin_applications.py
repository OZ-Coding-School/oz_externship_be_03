from typing import Any
from datetime import date
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.recruitments.models import Application, Recruitment
from apps.users.models import User
from apps.studies.models import StudyGroup


# 관리자용 지원서 API 테스트 케이스

class AdminApplicationViewTest(TestCase):
    def setUp(self) -> None:
        # 관리자, 모집 공고, 스터디 그룹, 지원자 생성
        self.client: APIClient = APIClient()
        self.admin: User = User.objects.create_user(
            email="admin@example.com",
            password="pass",
            birthday=date(1990, 1, 1),
            nickname="tester01",
            name="홍길동",
            phone_number="0123456789",
            gender="male",
        )
        self.client.force_authenticate(user=self.admin)

        self.study_group: StudyGroup = StudyGroup.objects.create(
            name="스터디 A",
            start_at="2025-01-01T00:00:00Z",
            end_at="2025-12-31T23:59:59Z",
        )

        self.recruitment: Recruitment = Recruitment.objects.create(
            title="모집 공고",
            author=self.admin,
            expected_headcount=5,
            close_at="2025-12-31T23:59:59Z",
            study_group=self.study_group,
            content="내용",
            estimated_fee=0,
        )

        self.applicant: User = User.objects.create_user(
            email="user@example.com",
            password="pass",
            birthday=date(2000, 1, 1)
        )

        self.application: Application = Application.objects.create(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="소개",
            motivation="동기",
            objective="목표",
            available_time="시간",
            has_study_experience=False,
        )

    def test_admin_application_list(self) -> None:
        # 관리자가 지원서 목록을 조회할 수 있는지 테스트
        url: str = reverse("admin-application-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_admin_application_detail(self) -> None:
        # 관리자가 특정 지원서 상세 정보를 조회할 수 있는지 테스트
        url: str = reverse("admin-application-detail", args=[self.application.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.application.id)

    def test_admin_application_approve(self) -> None:
        # 관리자가 지원서를 승인할 수 있는지 테스트
        url: str = reverse("admin-application-status", args=[self.application.id])
        response = self.client.patch(url, data={"status": "APPROVED"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "APPROVED")

    def test_admin_application_reject(self) -> None:
        # 관리자가 지원서를 거절할 수 있는지 테스트
        url: str = reverse("admin-application-status", args=[self.application.id])
        response = self.client.patch(url, data={"status": "REJECTED"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "REJECTED")