from typing import Any
from datetime import date
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.recruitments.models import Application, Recruitment
from apps.users.models import User


# 사용자용 지원서 API 테스트 케이스

class ApplicationUserViewTest(TestCase):
    def setUp(self) -> None:
        # 테스트용 사용자 및 모집 공고 생성
        self.client: APIClient = APIClient()
        self.user: User = User.objects.create_user(
            email="user@example.com",
            password="pass",
            birthday=date(2000, 1, 1)
        )
        self.client.force_authenticate(user=self.user)

        self.recruitment: Recruitment = Recruitment.objects.create(
            title="테스트 모집",
            author=self.user,
            expected_headcount=5,
            close_at="2099-12-31T23:59:59Z",
            content="내용",
            estimated_fee=0,
        )

    def test_create_application(self) -> None:
        # 사용자가 지원서를 작성할 수 있는지 테스트
        url: str = reverse("application-list-create")
        payload: dict[str, Any] = {
            "recruitment": self.recruitment.id,
            "self_introduction": "소개",
            "motivation": "동기",
            "objective": "목표",
            "available_time": "주말",
            "has_study_experience": True,
            "study_experience": "이전에 알고리즘 스터디 경험 있음",
        }
        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Application.objects.count(), 1)

    def test_withdraw_application(self) -> None:
        # 사용자가 지원서를 취소할 수 있는지 테스트
        app: Application = Application.objects.create(
            recruitment=self.recruitment,
            user=self.user,
            self_introduction="소개",
            motivation="동기",
            objective="목표",
            available_time="시간",
            has_study_experience=False,
            status="APPLIED",
        )
        url: str = reverse("application-withdraw", args=[app.id])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.status, "WITHDRAWN")

    def test_my_application_list(self) -> None:
        # 사용자가 본인의 지원서 목록을 조회할 수 있는지 테스트
        Application.objects.create(
            recruitment=self.recruitment,
            user=self.user,
            self_introduction="소개",
            motivation="동기",
            objective="목표",
            available_time="시간",
            has_study_experience=False,
            status="APPLIED",
        )
        url: str = reverse("application-my-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_my_application_detail(self) -> None:
        # 사용자가 본인의 지원서 상세 정보를 조회할 수 있는지 테스트
        app: Application = Application.objects.create(
            recruitment=self.recruitment,
            user=self.user,
            self_introduction="소개",
            motivation="동기",
            objective="목표",
            available_time="시간",
            has_study_experience=False,
        )
        url: str = reverse("application-my-detail", args=[app.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], app.id)