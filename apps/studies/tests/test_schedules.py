import uuid

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.studies.models.groups import StudyGroup
from apps.studies.models.schedules import GroupSchedule
from apps.users.models import User


class StudyScheduleAPITests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="pw1234",
            nickname="testuser",
            name="testuser",
            phone_number="01234567890",
            is_active=True,
            gender="M",
            birthday=timezone.now().strftime("%Y-%m-%d"),
        )

        self.group = StudyGroup.objects.create(
            name="테스트 그룹",
            max_headcount=5,
            start_at="2025-10-25T00:00:00Z",
            end_at="2025-10-30T00:00:00Z",
        )

    def test_unauthorized_cannot_create(self) -> None:
        """로그인하지 않은 사용자는 401"""
        url = reverse("studies:study-schedules-create")
        data = {
            "study_group": self.group.uuid,
            "title": "알고리즘 스터디",
            "objective": "탐색 알고리즘 학습",
            "session_date": "2025-10-28",
            "start_time": "14:00:00",
            "end_time": "16:00:00",
        }
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 401)

    def test_create_schedule_success(self) -> None:
        """로그인한 사용자는 스케줄 생성 가능"""
        self.client.force_authenticate(user=self.user)

        url = reverse("studies:study-schedules-create")
        data = {
            "study_group": self.group.uuid,
            "title": "자료구조 복습",
            "objective": "큐와 스택 복습",
            "session_date": "2025-10-27",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        }

        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(GroupSchedule.objects.count(), 1)
        self.assertTrue(GroupSchedule.objects.filter(title=data["title"], study_group=self.group).exists())

    def test_duplicate_schedule_conflict(self) -> None:
        """동일한 날짜/시간대 스케줄 중복 생성 방지 (409 Conflict)"""
        self.client.force_authenticate(user=self.user)
        url = reverse("studies:study-schedules-create")

        GroupSchedule.objects.create(
            study_group=self.group,
            title="중복 테스트",
            objective="테스트용",
            session_date="2025-10-28",
            start_time="10:00:00",
            end_time="12:00:00",
        )

        data = {
            "study_group": self.group.uuid,
            "title": "중복 테스트2",
            "objective": "테스트용2",
            "session_date": "2025-10-28",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        }

        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(GroupSchedule.objects.count(), 1)

    def test_invalid_time_validation(self) -> None:
        """종료 시간이 시작 시간보다 빠르면 400"""
        self.client.force_authenticate(user=self.user)
        url = reverse("studies:study-schedules-create")
        data = {
            "study_group": self.group.uuid,
            "title": "잘못된 시간",
            "objective": "시간 검증 테스트",
            "session_date": "2025-10-29",
            "start_time": "16:00:00",
            "end_time": "14:00:00",
        }
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_study_group_uuid(self) -> None:
        """study_group의 uuid에 해당하는 객체가 존재하지 않는 경우 400"""
        self.client.force_authenticate(user=self.user)
        url = reverse("studies:study-schedules-create")
        data = {
            "study_group": uuid.uuid4(),
            "title": "자료구조 복습",
            "objective": "큐와 스택 복습",
            "session_date": "2025-10-27",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        }
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["study_group"][0].code, "does_not_exist")
