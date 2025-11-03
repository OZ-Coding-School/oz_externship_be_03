from datetime import date
from uuid import UUID

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class StudyGroupListCreateViewTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.url = reverse("studies:study-group-list-create")

    def test_post_create_study_group(self) -> None:
        """POST 요청 테스트 - 상태 코드 201"""
        payload = {
            "name": "Test Group",
            "introduction": "This is Test Group",
            "profile_img_url": "https://example.com/test1.jpg",
            "max_headcount": 5,
            "start_at": "2027-11-01",  # 날짜 한참 뒤로 수정
            "end_at": "2028-11-10",  # 동일
            "status": "PENDING",
            "lectures": [1, 2],
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_study_group_list(self) -> None:
        """GET 요청 테스트 - 상태 코드 200 및 구조 확인"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(len(data), 10)

        first_group = data[0]
        self.assertIn("id", first_group)
        self.assertIn("name", first_group)
        self.assertIn("current_headcount", first_group)
        self.assertIn("max_headcount", first_group)
        self.assertIn("is_leader", first_group)
        self.assertIn("profile_img_url", first_group)
        self.assertIn("start_at", first_group)
        self.assertIn("end_at", first_group)
        self.assertIn("status", first_group)
        self.assertIn("lectures", first_group)


class StudyGroupDetailUpdateViewTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        group_id = "00000000-0000-0000-0000-000000000003"
        self.url = reverse("studies:study-group-detail-update", kwargs={"group_id": group_id})

    def test_get_detail_study_group(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertIn("current_headcount", data)
        self.assertIn("max_headcount", data)
        self.assertIn("members", data)
        self.assertIn("profile_img_url", data)
        self.assertIn("start_at", data)
        self.assertIn("end_at", data)
        self.assertIn("status", data)
        self.assertIn("lectures", data)


# REQ-STDY-006: 스터디 그룹 멤버 추방 API 테스트
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
        self.group_id = UUID("00000000-0000-0000-0000-000000000001")

    def test_kick_member_not_leader(self) -> None:
        """리더 아님 - 기본 요청"""
        url = reverse("studies:study-member-kick", kwargs={"group_id": self.group_id, "member_id": 1})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_member_invalid_member_id(self) -> None:
        """리더 아님 - 잘못된 멤버 ID(999)"""
        url = reverse("studies:study-member-kick", kwargs={"group_id": self.group_id, "member_id": 999})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_member_nonexistent_member_id(self) -> None:
        """리더 아님 - 존재하지 않는 멤버 ID(9999)"""
        url = reverse("studies:study-member-kick", kwargs={"group_id": self.group_id, "member_id": 9999})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_member_unauthenticated(self) -> None:
        """비인증 사용자"""
        self.client.logout()
        url = reverse("studies:study-member-kick", kwargs={"group_id": self.group_id, "member_id": 1})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# REQ-STDY-007: 스터디 그룹 자진 탈퇴 API 테스트
class MemberLeaveAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create(
            email="leave@test.com",
            name="탈퇴유저",
            nickname="leaveuser",
            phone_number="010-5678-1234",
            gender="FEMALE",
            birthday=date(1998, 2, 2),
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)
        self.group_id = UUID("00000000-0000-0000-0000-000000000001")
        self.url = reverse("studies:study-member-leave", kwargs={"group_id": self.group_id})

    def test_leave_group_authenticated(self) -> None:
        """로그인된 사용자가 탈퇴 요청"""
        response = self.client.delete(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_leave_group_unauthenticated(self) -> None:
        """비로그인 사용자가 탈퇴 요청"""
        self.client.logout()
        response = self.client.delete(self.url, data={"member_id": 1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# REQ-STDY-008: 스터디 그룹 리더 위임 API 테스트
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
        self.group_id = UUID("00000000-0000-0000-0000-000000000001")
        self.url = reverse("studies:delegate-leader", kwargs={"group_id": self.group_id})

    def test_delegate_leader_not_leader(self) -> None:
        """리더 아님 - 정상 ID(2)"""
        response = self.client.post(self.url, {"target_member_id": 2}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delegate_leader_invalid_id(self) -> None:
        """리더 아님 - 잘못된 ID(-1)"""
        response = self.client.post(self.url, {"target_member_id": -1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delegate_leader_no_permission(self) -> None:
        """리더 아님 - 권한 없음"""
        response = self.client.post(self.url, {"target_member_id": 2}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
