from datetime import date, datetime, timedelta
from unittest.mock import patch, AsyncMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.notifications.models import Notification
from apps.notifications.signals import notifications_created
from apps.recruitments.models.recruitments import Recruitment
from apps.recruitments.models.application import Application
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
            birthday=date(1995,1,11),
            gender=Gender.MALE
        )

        self.applicant = User.objects.create(
            email="applicant@test.com",
            password="test123",
            nickname="pythongosu",
            name="이지원자",
            phone_number="010-9876-5432",
            birthday=date(1995, 5, 15),
            gender=Gender.FEMALE
        )

        self.study_group = StudyGroup.objects.create(
            name="오즈 스터디",
            introduction="오즈 스터디 그룹",
            max_headcount=5,
            start_at=datetime(2020, 1, 1),
            end_at=datetime(2020, 5, 1),
        )

        self.recruitment = Recruitment.objects.create(
            study_group=self.study_group,
            author=self.author,
            title="Django 스터디 모집",
            content="Django를 함께 공부할 팀원을 모집합니다.",
            estimated_fee=50000,
            expected_headcount=5
        )
    @patch('apps.notifications.services.redis_pubsub_classify.notification_pubsub.publish_notification')
    def test_notifications_created_with_db_only(self,mock_publish:AsyncMock)->None:
        """Application 생성 시 DB 알림 생성 테스트"""

        Application.objects.create(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="안녕하세요. 백엔드 개발자 취직하고 싶습니다.",
            motivation="Django 프레임워크를 학습하고 실무 경험을 쌓고 싶습니다.",
            objective="풀스택 개발자로 성장하기",
            available_time="주 5회, 평일 오전 10:00 - 오후 2:00"
        )
        #DB에 Notification 생성 확인
        notification = Notification.objects.filter(
            user_id=self.author.id,
            type=Notification.NotificationType.APPLICATION_CREATED
        ).first()

        self.assertIsNotNone(notification,"알림이 생성되어야 합니다.")

        assert notification is not None

        expected_content = f"공고 '{self.recruitment.title}'에 새로운 지원자가 지원했습니다."
        self.assertEqual(notification.content,expected_content)
        self.assertIn(self.recruitment.title,notification.content)
        self.assertEqual(notification.type,Notification.NotificationType.APPLICATION_CREATED)
        self.assertFalse(notification.is_read)