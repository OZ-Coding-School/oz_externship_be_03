
from datetime import date, datetime, timezone, time, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import Notification
from apps.notifications.tasks import send_tomorrow_schedule_notifications, send_today_schedule_notifications
from apps.studies.models import StudyGroup, GroupSchedule, ScheduleParticipant
from apps.studies.models.groups import GroupMember
from apps.users.enums import Gender

User = get_user_model()

class ScheduleTasksTestCase(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@test.com",
            password="test123",
            nickname="user1",
            name="user1",
            phone_number="010-3456-7890",
            birthday=date(1995,1,1),
            gender=Gender.MALE,
        )

        self.user2 = User.objects.create_user(
            email="user2@test.com",
            password="test123",
            nickname="user2",
            name="user2",
            phone_number="010-3456-7891",
            birthday=date(1995,1,1),
            gender=Gender.MALE,
        )
        self.study_group = StudyGroup.objects.create(
            name="오즈코딩스쿨",
            introduction="장고 익스턴십",
            max_headcount=5,
            start_at=datetime.now(timezone.utc),
            end_at=datetime.now(timezone.utc),
        )

        self.member1 = GroupMember.objects.create(
            study_group=self.study_group,
            user=self.user1,
            is_leader=True,
        )

        self.member2 = GroupMember.objects.create(
            study_group=self.study_group,
            user=self.user2,
            is_leader=False,
        )

        today = date.today()
        tomorrow = today + timedelta(days=1)

        self.today_schedule = GroupSchedule.objects.create(
            study_group=self.study_group,
            title="자료형 학습",
            objective="파이썬 자료형 이해하기",
            session_date= today,
            start_time=time(9, 30),
            end_time=time(13, 30),
        )

        self.tomorrow_schedule = GroupSchedule.objects.create(
            study_group=self.study_group,
            title="자료형 학습",
            objective="파이썬 자료형 이해하기",
            session_date= tomorrow,
            start_time=time(9, 30),
            end_time=time(13, 30),
        )

        self.tomorrow_participant = ScheduleParticipant.objects.create(
            schedule=self.tomorrow_schedule,
            member=self.member1,
        )

        self.today_participant = ScheduleParticipant.objects.create(
            schedule=self.today_schedule,
            member=self.member2,
        )

    @patch("apps.notifications.tasks.send_to_pubsub.delay")
    def test_send_tomorrow_schedule_notifications(self, mock_send:MagicMock) -> None:
        """예정 스케줄 알림 테스트"""
        send_tomorrow_schedule_notifications()

        notifications = Notification.objects.filter(
            type=Notification.NotificationType.STUDY_SCHEDULE_UPCOMING
        )

        self.assertEqual(notifications.count(), 1)

        notification = notifications.get(user=self.user1)
        expected_content = "내일은 오즈코딩스쿨에서 자료형 학습이 예정되어 있습니다!"

        self.assertIn(expected_content, notification.content)
        self.assertIn("api/v1/studies/groups/",notification.back_url_link)

        self.assertEqual(mock_send.call_count, 1)
        mock_send.assert_any_call(notification.id)

    @patch("apps.notifications.tasks.send_to_pubsub.delay")
    def test_send_today_schedule_notifications(self, mock_send:MagicMock) -> None:
        """당일 스케줄 알림 테스트"""
        send_today_schedule_notifications()

        notifications = Notification.objects.filter(
            type = Notification.NotificationType.STUDY_SCHEDULE_TODAY
        )

        self.assertEqual(notifications.count(), 1)

        notification = notifications.get(user=self.user2)
        expected_content = "금일 09:30부터 13:30까지 오즈코딩스쿨에서 자료형 학습이 예정되어 있습니다!"

        self.assertIn(expected_content, notification.content)
        self.assertIn(f"/api/v1/studies/groups/", notification.back_url_link)

        self.assertEqual(mock_send.call_count, 1)
        mock_send.assert_any_call(notification.id)

