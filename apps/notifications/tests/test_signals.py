from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import Notification
from apps.recruitments.models import Recruitment
from apps.recruitments.models.application import Application, ApplicationStatus
from apps.users.enums import Gender

User = get_user_model()


class SignalTest(TestCase):

    def setUp(self):
        self.author = User.objects.create_user(
            email="author@test.com",
            password="test123",
            nickname="author",
            name="author",
            phone_number="010-1234-5679",
            birthday=date(1995, 1, 11),
            gender=Gender.MALE,
        )
        self.applicant = User.objects.create_user(
            email="applicant_{unique_id}@test1.com",
            password="test123",
            nickname="applicant",
            name="applicant",
            phone_number="010-1234-5678",
            birthday=date(1995, 1, 12),
            gender=Gender.MALE,
        )
        self.recruitment = Recruitment.objects.create(
            title="오즈코딩스쿨 모집",
            author=self.author,
            content="테스트 공고",
            estimated_fee=100000,
            expected_headcount=5,
        )

    @patch("apps.notifications.signals.send_to_pubsub.delay")
    def test_application_created_notification(self, mock_task):
        """지원 생성시 공고 작성자에게 보낼 알림 생성 테스트"""
        application = Application.objects.create(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="자기소개",
            motivation="지원동기",
            objective="목표",
            available_time="시간",
        )

        notification = Notification.objects.get(
            user=self.author, type=Notification.NotificationType.APPLICATION_CREATED
        )

        self.assertEqual(notification.content, f"공고 '{self.recruitment.title}'에 새로운 지원자가 지원했습니다.")
        mock_task.assert_called_once_with(notification.id)

    @patch("apps.notifications.signals.send_to_pubsub.delay")
    def test_application_approved_notification(self, mock_task):
        """지원 승인 알림 생성 테스트"""
        application = Application.objects.create(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="자기소개",
            motivation="지원동기",
            objective="목표",
            available_time="시간",
        )

        application.status = ApplicationStatus.APPROVED
        application.save()

        notification = Notification.objects.get(
            user=self.applicant, type=Notification.NotificationType.APPLICATION_STATUS_APPROVAL
        )

        self.assertEqual(
            notification.content, f"'{self.recruitment.title}' 구인 공고에 대한 지원내역이 승인되었습니다."
        )
        self.assertEqual(mock_task.call_count, 2)

    @patch("apps.notifications.signals.send_to_pubsub.delay")
    def test_application_rejected_notification(self, mock_task):
        """지원 거절 알림 생성 테스트"""
        application = Application.objects.create(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="자기소개",
            motivation="지원동기",
            objective="목표",
            available_time="시간",
        )

        application.status = ApplicationStatus.REJECTED
        application.save()

        notification = Notification.objects.get(
            user=self.applicant, type=Notification.NotificationType.APPLICATION_STATUS_REJECTION
        )

        self.assertEqual(
            notification.content, f"'{self.recruitment.title}' 구인 공고에 대한 지원내역이 거절되었습니다."
        )
        self.assertEqual(mock_task.call_count, 2)
