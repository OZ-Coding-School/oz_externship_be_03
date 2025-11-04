import typing
from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recruitments.models.application import Application
from apps.recruitments.models.recruitments import Recruitment
from apps.users.models import User


class ApplicationAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass",
            birthday=date(2000, 1, 1),
            name="테스트유저",
            nickname="tester",
            phone_number="010-1234-5678",
            gender="MALE",
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

        self.recruitment = Recruitment.objects.create(
            title="테스트 스터디 모집", content="스터디 내용", author=self.user, estimated_fee=0, expected_headcount=5
        )

    def test_create_application_success(self) -> None:
        url = reverse("application-list-create")
        payload = {
            "recruitment": self.recruitment.id,
            "objective": "스터디 참여",
            "motivation": "열심히 배우고 싶음",
            "self_introduction": "저는 준호입니다",
            "available_time": "주말",
            "has_study_experience": False,
            "study_experience": "",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        application = Application.objects.first()
        self.assertIsNotNone(application)
        application = typing.cast(Application, application)
        self.assertEqual(application.objective, "스터디 참여")
