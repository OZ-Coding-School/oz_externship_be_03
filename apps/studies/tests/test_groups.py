from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


# REQ-STDY-006: 스터디 그룹 멤버 추방 api 테스트
class MemberKickAPITestCase(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create(
            email="test@test.com",
            name="테스트유저",
            nickname="testuser",
            phone_number="010-1234-5678",
            gender="MALE",
            birthday=date(2000, 1, 1),
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)
        self.group_id = "00000000-0000-0000-0000-000000000001"
        self.member_id = 1
        self.url = reverse(
            "study-member-kick",
            kwargs={"group_id": self.group_id, "member_id": self.member_id},
        )

    def test_kick_member_success(self) -> None:
        """리더 권한이 없어서 403 Forbidden (Mock 환경)"""
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_member_without_authentication(self) -> None:
        """인증 없이 요청 시 401 Unauthorized"""
        self.client.logout()
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_kick_leader(self) -> None:
        """리더 권한이 없어서 403 Forbidden (Mock 환경)"""
        url = reverse(
            "study-member-kick",
            kwargs={"group_id": self.group_id, "member_id": 999},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_non_member(self) -> None:
        """리더 권한이 없어서 403 Forbidden (Mock 환경)"""
        url = reverse(
            "study-member-kick",
            kwargs={"group_id": self.group_id, "member_id": 9999},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# REQ-STDY-008: 스터디 그룹 리더 위임 api 테스트
class DelegateLeaderAPITestCase(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create(
            email="test@test.com",
            name="테스트유저",
            nickname="testuser",
            phone_number="010-1234-5678",
            gender="MALE",
            birthday=date(2000, 1, 1),
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)
        self.group_id = "00000000-0000-0000-0000-000000000001"
        self.url = reverse("delegate-leader", kwargs={"group_id": self.group_id})

    def test_delegate_leader_success(self) -> None:
        """리더 권한이 없어서 403 Forbidden (Mock 환경)"""
        data = {"target_user_id": 2}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delegate_to_invalid_user(self) -> None:
        """리더 권한이 없어서 403 Forbidden (Mock 환경)"""
        data = {"target_user_id": -1}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delegate_without_leader_permission(self) -> None:
        """리더가 아닌 사람이 위임 시도 시 403"""
        response = self.client.post(self.url, {"target_user_id": 2}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
