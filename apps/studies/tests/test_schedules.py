from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.studies.models.groups import StudyGroup
from apps.studies.models.schedules import StudySchedule


class StudyScheduleTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="user1", password="test1234")

        self.group = StudyGroup.objects.create(
            name="테스트 그룹",
            max_headcount=5,
            start_at="2025-10-25T00:00:00Z",
            end_at="2025-10-30T00:00:00Z",
        )

    def test_unauthorized_cannot_create(self):
        """로그인하지 않은 사용자는 401"""
        url = f"/api/v1/studies/groups/{self.group.uuid}/schedules/"
        data = {
            "title": "알고리즘 스터디",
            "objective": "탐색 알고리즘 학습",
            "session_date": "2025-10-28",
            "start_time": "14:00:00",
            "end_time": "16:00:00",
        }
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 401)

    def test_create_schedule_success(self):
        """로그인한 사용자는 스케줄 생성 가능"""
        self.client.force_authenticate(user=self.user)

        url = f"/api/v1/studies/groups/{self.group.uuid}/schedules/"
        data = {
            "title": "자료구조 복습",
            "objective": "큐와 스택 복습",
            "session_date": "2025-10-27",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        }

        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(StudySchedule.objects.count(), 1)
        schedule = StudySchedule.objects.first()
        self.assertEqual(schedule.title, "자료구조 복습")

    def test_duplicate_schedule_conflict(self):
        """동일한 날짜/시간대 스케줄 중복 생성 방지 (409 Conflict)"""
        self.client.force_authenticate(user=self.user)

        StudySchedule.objects.create(
            study_group=self.group,
            title="중복 테스트",
            objective="테스트용",
            session_date="2025-10-28",
            start_time="10:00:00",
            end_time="12:00:00",
        )

        url = f"/api/v1/studies/groups/{self.group.uuid}/schedules/"
        data = {
            "title": "중복 테스트2",
            "objective": "테스트용2",
            "session_date": "2025-10-28",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        }

        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(StudySchedule.objects.count(), 1)

    def test_invalid_time_validation(self):
        """종료 시간이 시작 시간보다 빠르면 400"""
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/studies/groups/{self.group.uuid}/schedules/"
        data = {
            "title": "잘못된 시간",
            "objective": "시간 검증 테스트",
            "session_date": "2025-10-29",
            "start_time": "16:00:00",
            "end_time": "14:00:00",
        }
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 400)
