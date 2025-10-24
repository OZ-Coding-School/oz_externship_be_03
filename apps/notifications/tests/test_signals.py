from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.signals import notifications_created
from apps.recruitments.models.application import Application
from apps.recruitments.models.recruitments import Recruitment
from apps.studies.models.groups import StudyGroup
from apps.users.enums import Gender

User = get_user_model()


class NotificationsCreatedSignalTest(TestCase):
    def setUp(self) -> None:
        self.author = User.objects.create(
            email="author@test.com",
            password="test123",
            nickname="lee",
            name="오즈",
            phone_number="010-3456-7890",
            birthday=date(1995, 1, 11),
            gender=Gender.MALE,
        )

        self.applicant = User.objects.create(
            email="applicant@test.com",
            password="test123",
            nickname="pythongosu",
            name="이지원자",
            phone_number="010-9876-5432",
            birthday=date(1995, 5, 15),
            gender=Gender.FEMALE,
        )

        self.study_group = StudyGroup.objects.create(
            name="오즈 스터디",
            introduction="오즈 스터디 그룹",
            max_headcount=5,
            start_at=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
            end_at=datetime(2020, 5, 1, tzinfo=ZoneInfo("UTC")),
        )

        self.recruitment = Recruitment.objects.create(
            study_group=self.study_group,
            author=self.author,
            title="Django 스터디 모집",
            content="Django를 함께 공부할 팀원을 모집합니다.",
            estimated_fee=50000,
            expected_headcount=5,
        )

    @patch("apps.notifications.services.redis_pubsub_classify.notification_pubsub.publish_notification")
    def test_notifications_created_with_db_only(self, mock_publish: AsyncMock) -> None:
        """Application 생성 시 DB 알림 생성 테스트"""

        Application.objects.create(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="안녕하세요. 백엔드 개발자 취직하고 싶습니다.",
            motivation="Django 프레임워크를 학습하고 실무 경험을 쌓고 싶습니다.",
            objective="풀스택 개발자로 성장하기",
            available_time="주 5회, 평일 오전 10:00 - 오후 2:00",
        )
        # DB에 Notification 생성 확인
        notification = Notification.objects.filter(
            user_id=self.author.id, type=Notification.NotificationType.APPLICATION_CREATED
        ).first()

        self.assertIsNotNone(notification, "알림이 생성되어야 합니다.")

        assert notification is not None

        expected_content = f"공고 '{self.recruitment.title}'에 새로운 지원자가 지원했습니다."
        self.assertEqual(notification.content, expected_content)
        self.assertIn(self.recruitment.title, notification.content)
        self.assertEqual(notification.type, Notification.NotificationType.APPLICATION_CREATED)
        self.assertFalse(notification.is_read)
        self.assertIsNotNone(notification.back_url_link, "back_url_link가 설정되어야 합니다")
        self.assertIsInstance(notification.created_at, datetime, "created_at이 datetime 객체여야 합니다")
        self.assertEqual(notification.user_id, self.author.id, "알림 수신자가 올바르게 설정되어야 합니다")

    @patch("apps.notifications.services.redis_pubsub_classify.notification_pubsub.publish_notification")
    def test_signal_function_direct_call(self, mock_publish: AsyncMock) -> None:
        # Application 인스턴스 생성 (DB 저장하지 않음)
        fake_application = Application(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="시그널 함수 직접 호출 테스트용 자기소개",
            motivation="coverage 확보를 위한 테스트",
            objective="테스트 완료하기",
            available_time="테스트 시간",
        )

        # 시그널 함수 직접 호출 (created=True)
        notifications_created(sender=Application, instance=fake_application, created=True)

        # Notification 생성 확인
        notification = Notification.objects.filter(
            user_id=self.author.id, type=Notification.NotificationType.APPLICATION_CREATED
        ).first()

        self.assertIsNotNone(notification, "시그널 직접 호출 시 알림이 생성되어야 합니다")

        # mypy를 위한 타입 단언
        assert notification is not None

        self.assertEqual(notification.user_id, self.author.id)
        self.assertIn(self.recruitment.title, notification.content)

    @patch("apps.notifications.services.redis_pubsub_classify.notification_pubsub.publish_notification")
    def test_signal_function_created_false(self, mock_publish: AsyncMock) -> None:
        """시그널 함수 created=False 케이스 테스트"""
        fake_application = Application(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="created=False 테스트용",
            motivation="수정 시나리오 테스트를 위한 내용",
            objective="알림 미생성 확인하기",
            available_time="테스트용 시간",
        )

        initial_count = Notification.objects.count()

        # created=False로 시그널 호출
        notifications_created(sender=Application, instance=fake_application, created=False)

        final_count = Notification.objects.count()
        self.assertEqual(initial_count, final_count, "created=False일 때는 알림이 생성되지 않아야 합니다")

        # Redis publish도 호출되지 않았는지 확인
        mock_publish.assert_not_called()
