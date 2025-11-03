from datetime import date, timezone, datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import Notification
from apps.recruitments.models import Recruitment
from apps.recruitments.models.application import Application, ApplicationStatus
from apps.studies.models import StudyGroup
from apps.users.enums import Gender

User = get_user_model()


class SignalTest(TestCase):

    def setUp(self) -> None:
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

        self.study_group = StudyGroup.objects.create(
            name="오즈코딩스쿨",
            introduction="장고 익스턴십",
            max_headcount=5,
            start_at=datetime.now(timezone.utc),
            end_at=datetime.now(timezone.utc),
        )

    @patch("apps.notifications.signals.send_to_pubsub.delay")
    def test_application_created_notification(self, mock_task: MagicMock) -> None:
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
    def test_application_approved_notification(self, mock_task: MagicMock) -> None:
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
    def test_application_rejected_notification(self, mock_task: MagicMock) -> None:
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

    @patch('apps.notifications.tasks.send_study_group_notification.delay')
    def test_study_group_notification(self,mock_delay: MagicMock) -> None:
        """스터디 그룹 멤버 참여 알림 테스트"""
        self.recruitment.study_group = self.study_group
        self.recruitment.save()

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
            user=self.applicant,
            type=Notification.NotificationType.STUDY_MEMBER_JOINED
        )

        expected_content = f"{self.study_group.name}에 {self.applicant.nickname}님이 참여했습니다. 환영해주세요!"
        self.assertEqual(notification.content,expected_content)
        self.assertIn(f"/api/v1/chat/ws/study-groups/{self.study_group.id}",notification.back_url_link)

        mock_delay.assert_called_once_with(notification.id, self.study_group.id)


