from __future__ import annotations

import uuid as _uuid
from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.recruitments.models.application import ApplicationStatus
from apps.recruitments.models.recruitments import Recruitment
from apps.users.enums import Gender

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()


class ApplicationCreateAPITests(APITestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()

        # 작성자/지원자 준비
        self.author = User.objects.create_user(
            email="author@example.com",
            password="pw1234!!",
            nickname="author",
            name="작성자",
            phone_number="01011112222",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )
        self.user = User.objects.create_user(
            email="user@example.com",
            password="pw1234!!",
            nickname="user",
            name="지원자",
            phone_number="01011112223",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )

        # 마감되지 않은 공고
        self.recruitment = Recruitment.objects.create(
            author=self.author,
            title="웹 개발 스터디 모집",
            content="내용",
            estimated_fee=0,
            expected_headcount=5,
            close_at=timezone.now() + timedelta(days=7),
            is_closed=False,
        )

        self.url = reverse(
            "recruitments:recruitment-application-create", kwargs={"recruitment_uuid": self.recruitment.uuid}
        )

        self.payload_ok = {
            "self_introduction": "저는 백엔드 개발 경험이 있습니다.",
            "motivation": "팀 프로젝트를 통해 실력을 쌓고 싶습니다.",
            "objective": "스터디 참여 후 Django 프로젝트 완성",
            "available_time": "화/목 19:00~22:00",
            "has_study_experience": True,
            "study_experience": "이전 팀 프로젝트 CRUD 경험",
        }

    def auth(self, user: UserModel) -> None:
        self.client.force_authenticate(user=user)

    def test_unauthorized_401(self) -> None:
        response = self.client.post(self.url, data=self.payload_ok, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_success_201(self) -> None:
        self.auth(self.user)
        response = self.client.post(self.url, data=self.payload_ok, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        # 래핑 구조 확인
        self.assertIn("detail", body)
        self.assertIn("data", body)
        data = body["data"]

        # 필드 검증 (응답 시리얼라이저 스펙)
        self.assertEqual(data["recruitment_uuid"], str(self.recruitment.uuid))
        self.assertEqual(data["recruitment_title"], "웹 개발 스터디 모집")
        # 사용자 모델에 uuid 필드가 없을 수도 있으므로 존재만 체크(없으면 null)
        self.assertIn("user_uuid", data)

        # 상태 기본값 (모델 기본값 PENDING)
        self.assertEqual(data["status"], ApplicationStatus.PENDING)  # "PENDING"

        # 입력 필드 반영
        for key in [
            "self_introduction",
            "motivation",
            "objective",
            "available_time",
            "has_study_experience",
            "study_experience",
        ]:
            self.assertEqual(data[key], self.payload_ok[key])

        # 생성 시각 존재
        self.assertIn("created_at", data)

    def test_not_found_recruitment_404(self) -> None:
        self.auth(self.user)
        bad_url = reverse("recruitments:recruitment-application-create", kwargs={"recruitment_uuid": _uuid.uuid4()})
        response = self.client.post(bad_url, data=self.payload_ok, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.json())

    def test_closed_recruitment_400_by_flag(self) -> None:
        self.auth(self.user)
        # is_closed = True
        self.recruitment.is_closed = True
        self.recruitment.save(update_fields=["is_closed"])

        response = self.client.post(self.url, data=self.payload_ok, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    def test_closed_recruitment_400_by_close_at(self) -> None:
        self.auth(self.user)
        # close_at 경과
        self.recruitment.close_at = timezone.now() - timedelta(seconds=1)
        self.recruitment.save(update_fields=["close_at"])

        response = self.client.post(self.url, data=self.payload_ok, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    def test_author_cannot_apply_own_recruitment_400(self) -> None:
        self.auth(self.author)
        response = self.client.post(self.url, data=self.payload_ok, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    def test_duplicate_application_conflict_409(self) -> None:
        self.auth(self.user)
        # 1차 성공
        response1 = self.client.post(self.url, data=self.payload_ok, format="json")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # 2차 동일 지원 → Conflict
        response2 = self.client.post(self.url, data=self.payload_ok, format="json")
        self.assertEqual(response2.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("error", response2.json())
