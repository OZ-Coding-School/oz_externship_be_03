import json

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


# REQ-STDY-006: 스터디 그룹 멤버 추방 api 테스트
class MemberKickAPITestCase(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
        self.group_id = "00000000-0000-0000-0000-000000000001"
        self.member_id = 1
        self.url = reverse(
            "study-member-kick",
            kwargs={"group_id": self.group_id, "member_id": self.member_id},
        )

    def test_kick_member_success(self) -> None:
        """정상적으로 멤버를 추방했을 때 200 OK 응답"""
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 200)
        self.assertEqual(data["message"], "스터디 그룹 멤버를 추방했습니다.")

    def test_kick_member_invalid_uuid(self) -> None:
        """잘못된 UUID로 요청 시 400 Bad Request"""
        invalid_url = reverse(
            "study-member-kick",
            kwargs={"group_id": "invalid-uuid", "member_id": self.member_id},
        )
        response = self.client.delete(invalid_url)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_kick_member_without_authentication(self) -> None:
        """인증 없이 요청 시 401 Unauthorized"""
        self.client.logout()
        response = self.client.delete(self.url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_kick_leader(self) -> None:
        """리더를 추방하려고 시도할 때 400 에러"""
        # leader_id를 member_id로 설정
        url = reverse("study-member-kick", kwargs={"group_id": self.group_id, "member_id": 999})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kick_non_member(self) -> None:
        """그룹에 속하지 않은 사람 추방 시도 시 404"""
        url = reverse("study-member-kick", kwargs={"group_id": self.group_id, "member_id": 9999})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# REQ-STDY-008: 스터디 그룹 리더 위임 api 테스트
class DelegateLeaderAPITestCase(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
        self.group_id = 1
        self.url = reverse("study-delegate-leader", kwargs={"group_id": self.group_id})

    def test_delegate_leader_success(self) -> None:
        """정상적으로 리더를 위임했을 때 200 OK"""
        data = {"target_user_id": 2}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delegate_to_invalid_user(self) -> None:
        """유효하지 않은 유저에게 위임 시도 시 400"""
        data = {"target_user_id": -1}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
