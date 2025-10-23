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

    def test_kick_member_forbidden_cases(self) -> None:
        """리더 권한이 없거나 인증이 없는 경우 403/401 반환"""
        cases = [
            {
                "label": "리더 아님 - 기본 요청",
                "auth": True,
                "member_id": 1,
                "expected": status.HTTP_403_FORBIDDEN,
            },
            {
                "label": "리더 아님 - 잘못된 멤버 ID(999)",
                "auth": True,
                "member_id": 999,
                "expected": status.HTTP_403_FORBIDDEN,
            },
            {
                "label": "리더 아님 - 존재하지 않는 멤버 ID(9999)",
                "auth": True,
                "member_id": 9999,
                "expected": status.HTTP_403_FORBIDDEN,
            },
            {
                "label": "비인증 사용자",
                "auth": False,
                "member_id": 1,
                "expected": status.HTTP_401_UNAUTHORIZED,
            },
        ]

        for case in cases:
            with self.subTest(msg=case["label"]):
                if not case["auth"]:
                    self.client.logout()
                url = reverse(
                    "study-member-kick",
                    kwargs={
                        "group_id": self.group_id,
                        "member_id": case["member_id"],
                    },
                )
                response = self.client.delete(url)
                self.assertEqual(response.status_code, case["expected"])


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

    def test_delegate_leader_forbidden_cases(self) -> None:
        """리더가 아니거나 잘못된 입력값인 경우 403 반환"""
        cases = [
            {
                "label": "리더 아님 - 정상 ID(2)",
                "data": {"target_member_id": 2},
                "expected": status.HTTP_403_FORBIDDEN,
            },
            {
                "label": "리더 아님 - 잘못된 ID(-1)",
                "data": {"target_member_id": -1},
                "expected": status.HTTP_403_FORBIDDEN,
            },
            {
                "label": "리더 아님 - 권한 없음",
                "data": {"target_member_id": 2},
                "expected": status.HTTP_403_FORBIDDEN,
            },
        ]

        for case in cases:
            with self.subTest(msg=case["label"]):
                response = self.client.post(self.url, case["data"], format="json")
                self.assertEqual(response.status_code, case["expected"])
