from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.recruitments.models import Application, ApplicationStatus, Recruitment
from apps.users.enums import Gender

User = get_user_model()


class ApplicationWithdrawAPIViewTests(APITestCase):
    def setUp(self) -> None:
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

        # 공고 4개
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
        self.recruitment3 = Recruitment.objects.create(
            author=self.user,
            title="멋진 개발자",
            content="...",
            estimated_fee=0,
            expected_headcount=4,
            close_at=now + timedelta(days=5),
        )
        self.recruitment4 = Recruitment.objects.create(
            author=self.user,
            title="끝내주는 개발자",
            content="...",
            estimated_fee=0,
            expected_headcount=4,
            close_at=now + timedelta(days=5),
        )

        # 신청서 4개: 대기/승인/거절/취소
        self.pending_application = Application.objects.create(
            recruitment=self.recruitment1,
            user=self.user,
            self_introduction="...",
            motivation="...",
            objective="...",
            available_time="...",
            status=ApplicationStatus.PENDING,
        )
        self.approved_application = Application.objects.create(
            recruitment=self.recruitment2,
            user=self.user,
            self_introduction="...",
            motivation="...",
            objective="...",
            available_time="...",
            status=ApplicationStatus.APPROVED,
        )
        self.rejected_application = Application.objects.create(
            recruitment=self.recruitment3,
            user=self.user,
            self_introduction="...",
            motivation="...",
            objective="...",
            available_time="...",
            status=ApplicationStatus.REJECTED,
        )
        self.canceled_application = Application.objects.create(
            recruitment=self.recruitment4,
            user=self.user,
            self_introduction="...",
            motivation="...",
            objective="...",
            available_time="...",
            status=ApplicationStatus.CANCELED,
        )

        self.url_pending = reverse(
            "recruitments:application-withdraw", kwargs={"application_uuid": str(self.pending_application.uuid)}
        )
        self.url_approved = reverse(
            "recruitments:application-withdraw", kwargs={"application_uuid": str(self.approved_application.uuid)}
        )
        self.url_rejected = reverse(
            "recruitments:application-withdraw", kwargs={"application_uuid": str(self.rejected_application.uuid)}
        )
        self.url_canceled = reverse(
            "recruitments:application-withdraw", kwargs={"application_uuid": str(self.canceled_application.uuid)}
        )

    # === 성공 ===
    def test_withdraw_success_from_pending(self) -> None:
        self.client.force_authenticate(self.user)

        resp = self.client.patch(self.url_pending)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        body = resp.json()
        self.assertIn("detail", body)
        self.assertIn("data", body)
        self.assertIn("uuid", body["data"])
        self.assertIn("status", body["data"])
        self.assertEqual(body["data"]["status"], ApplicationStatus.CANCELED)

        # DB 반영 확인
        self.pending_application.refresh_from_db()
        self.assertEqual(self.pending_application.status, ApplicationStatus.CANCELED)

    # === 권한 ===
    def test_withdraw_forbidden_when_not_user(self) -> None:
        self.client.force_authenticate(self.other)

        resp = self.client.patch(self.url_pending)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", resp.json())

        # 상태 변화 없음
        self.pending_application.refresh_from_db()
        self.assertEqual(self.pending_application.status, ApplicationStatus.PENDING)

    # === 잘못된 상태 ===
    def test_withdraw_bad_request_when_approved(self) -> None:
        self.client.force_authenticate(self.user)

        resp = self.client.patch(self.url_approved)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        self.assertIn("error", body)

        self.approved_application.refresh_from_db()
        self.assertEqual(self.approved_application.status, ApplicationStatus.APPROVED)

    def test_withdraw_bad_request_when_rejected(self) -> None:
        self.client.force_authenticate(self.user)

        resp = self.client.patch(self.url_rejected)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.json())

        self.rejected_application.refresh_from_db()
        self.assertEqual(self.rejected_application.status, ApplicationStatus.REJECTED)

    def test_withdraw_bad_request_when_already_canceled(self) -> None:
        self.client.force_authenticate(self.user)

        resp = self.client.patch(self.url_canceled)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.json())

        self.canceled_application.refresh_from_db()
        self.assertEqual(self.canceled_application.status, ApplicationStatus.CANCELED)

    # === 미존재 ===
    def test_withdraw_not_found(self) -> None:
        self.client.force_authenticate(self.user)

        url = reverse("recruitments:application-withdraw", kwargs={"application_uuid": str(uuid4())})
        resp = self.client.patch(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", resp.json())
