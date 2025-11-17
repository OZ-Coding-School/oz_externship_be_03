from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.recruitments.models.application import Application, ApplicationStatus
from apps.recruitments.models.recruitment_images import RecruitmentImage
from apps.recruitments.models.recruitments import Recruitment
from apps.users.enums import Gender

User = get_user_model()


class MyApplicationsAPITests(APITestCase):
    def setUp(self) -> None:
        self.url = reverse("recruitments:my-applications")

        # 사용자 2명
        self.user = User.objects.create_user(
            email="user@example.com",
            password="pw1234!!",
            nickname="user",
            name="사용자",
            phone_number="01011112223",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="pw1234!!",
            nickname="other",
            name="다른사용자",
            phone_number="01011112222",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )

        # 공고 2개 (마감일 다르게)
        now = timezone.now()
        self.recruitment1 = Recruitment.objects.create(
            author=self.user,
            title="백엔드 개발자",
            content="...",
            estimated_fee=0,
            expected_headcount=6,
            close_at=now + timedelta(days=10),
        )
        self.recruitment2 = Recruitment.objects.create(
            author=self.user,
            title="프론트엔드 개발자",
            content="...",
            estimated_fee=0,
            expected_headcount=4,
            close_at=now + timedelta(days=5),
        )

        # recruitment1에는 이미지 1장, recruitment2에는 이미지 없음
        RecruitmentImage.objects.create(recruitment=self.recruitment1, img_url="https://cdn.example.com/study.png")

        # 내 지원 2건 (생성 순서대로 created_at 증가)
        self.first_application = Application.objects.create(
            recruitment=self.recruitment1,
            user=self.user,
            self_introduction="...",
            motivation="...",
            objective="...",
            available_time="...",
            status=ApplicationStatus.APPROVED,
        )
        self.second_application = Application.objects.create(
            recruitment=self.recruitment2,
            user=self.user,
            self_introduction="...",
            motivation="...",
            objective="...",
            available_time="...",
            status=ApplicationStatus.PENDING,
        )

        # 다른 사용자의 지원 1건 (내 목록에 포함되면 안 됨)
        Application.objects.create(
            recruitment=self.recruitment1,
            user=self.other,
            self_introduction="...",
            motivation="...",
            objective="...",
            available_time="...",
            status=ApplicationStatus.PENDING,
        )

    # ==============================
    # 지원 목록 조회 API 테스트
    # ==============================
    def test_auth_required(self) -> None:
        """인증 없이 접근하면 401"""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_my_applications_happy_path(self) -> None:
        """내 지원 목록을 최신순으로, 지정 스펙대로 응답"""
        self.client.force_authenticate(self.user)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        body: dict[str, Any] = resp.json()
        self.assertIn("detail", body)
        self.assertIn("data", body)
        items = body["data"]
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 2)  # 내 지원 2건만

        # 최신순: 마지막에 만든 second_application(프론트)가 먼저
        first, second = items[0], items[1]
        self.assertEqual(first["recruitment_title"], "프론트엔드 개발자")
        self.assertEqual(second["recruitment_title"], "백엔드 개발자")

        # 필드 존재/타입 체크
        for it in items:
            self.assertIn("uuid", it)  # Application.uuid (UUID 문자열)
            self.assertIsInstance(it["uuid"], str)
            self.assertIn("status", it)  # enum 문자열
            self.assertIn(it["status"], ["PENDING", "APPROVED", "REJECTED", "CANCELED"])
            self.assertIn("created_at", it)  # ISO-8601 문자열(UTC Z는 포맷 정책에 따름)
            self.assertIn("recruitment_title", it)
            self.assertIn("recruitment_img", it)  # 첫 이미지 또는 None
            self.assertIn("expected_headcount", it)
            self.assertIn("deadline", it)  # YYYY-MM-DD

            self.assertIn("lectures", it)
            self.assertIsInstance(it["lectures"], list)
            for lec in it["lectures"]:
                self.assertIsInstance(lec, str)

            self.assertIn("tags", it)
            self.assertIsInstance(it["tags"], list)
            for tag in it["tags"]:
                self.assertIsInstance(tag, str)

        # 이미지 규칙: recruitment1만 이미지 존재 → 해당 아이템에서는 URL, 다른 하나는 null
        # second가 recruitment1(백엔드)이므로 이미지 있음
        self.assertEqual(second["recruitment_img"], "https://cdn.example.com/study.png")
        # first가 recruitment2(프론트)므로 이미지 없음 → None
        self.assertIsNone(first["recruitment_img"])

    # ==============================
    # 지원 상세 조회 API 테스트
    # ==============================
    def test_detail_requires_auth(self) -> None:
        """인증 없이 상세 접근하면 401"""
        url = reverse("recruitments:my-application-detail", args=[self.first_application.uuid])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_happy_path(self) -> None:
        """내 지원서 상세를 스펙대로 반환"""
        self.client.force_authenticate(self.user)
        # 이미지가 있는 recruitment1에 연결된 지원서로 검증
        url = reverse("recruitments:my-application-detail", args=[self.first_application.uuid])

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        body: dict[str, Any] = resp.json()
        self.assertIn("detail", body)
        self.assertIn("data", body)
        data = body["data"]

        # 상위 필드 존재
        for key in [
            "uuid",
            "status",
            "created_at",
            "self_introduction",
            "motivation",
            "objective",
            "available_time",
            "has_study_experience",
            "study_experience",
            "recruitment",
        ]:
            self.assertIn(key, data)

        # 타입/값 일부 확인
        self.assertEqual(data["uuid"], str(self.first_application.uuid))
        self.assertIn(data["status"], ["PENDING", "APPROVED", "REJECTED", "CANCELED"])

        # recruitment 서브오브젝트 검증
        rec = data["recruitment"]
        for key in ["uuid", "title", "recruitment_img", "expected_headcount", "deadline"]:
            self.assertIn(key, rec)

        self.assertEqual(rec["uuid"], str(self.recruitment1.uuid))
        self.assertEqual(rec["title"], self.recruitment1.title)
        self.assertEqual(rec["recruitment_img"], "https://cdn.example.com/study.png")  # 첫 이미지
        self.assertEqual(rec["expected_headcount"], self.recruitment1.expected_headcount)
        self.assertEqual(rec["deadline"], self.recruitment1.close_at.date().isoformat())

    def test_detail_404_when_not_mine(self) -> None:
        """내 소유가 아닌 지원서 요청 시 404"""
        self.client.force_authenticate(self.user)
        other_app = Application.objects.filter(user=self.other).first()
        self.assertIsNotNone(other_app)
        assert other_app is not None  # mypy용 명시
        url = reverse("recruitments:my-application-detail", args=[other_app.uuid])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
