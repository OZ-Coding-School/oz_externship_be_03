from datetime import date, datetime, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class MemberFeatureAPITestCase(APITestCase):
    """REQ-STDY-006~008: 스터디 그룹 멤버 관련 기능 통합 테스트"""

    def setUp(self) -> None:
        self.client = APIClient()

        # 사용자 생성 (gender는 실제 choices 값 사용)
        self.leader = User.objects.create(
            email="leader@test.com",
            name="리더유저",
            nickname="leaderuser",
            phone_number="010-1111-1111",
            gender="M",
            birthday=date(1995, 5, 5),
            is_active=True,
        )
        self.member = User.objects.create(
            email="member@test.com",
            name="멤버유저",
            nickname="memberuser",
            phone_number="010-2222-2222",
            gender="F",
            birthday=date(1998, 8, 8),
            is_active=True,
        )
        self.outsider = User.objects.create(
            email="outsider@test.com",
            name="외부유저",
            nickname="outsider",
            phone_number="010-0000-0000",
            gender="M",
            birthday=date(1999, 1, 1),
            is_active=True,
        )

        # 그룹 생성 (uuid 자동 생성)
        self.group = StudyGroup.objects.create(
            name="통합테스트 그룹",
            start_at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
            end_at=timezone.make_aware(datetime.combine(date.today() + timedelta(days=7), datetime.min.time())),
        )

        # 멤버 등록
        self.leader_member = GroupMember.objects.create(study_group=self.group, user=self.leader, is_leader=True)
        self.member_member = GroupMember.objects.create(study_group=self.group, user=self.member, is_leader=False)

        # 로그인
        self.client.force_authenticate(user=self.leader)

    # REQ-STDY-006: 스터디 그룹 멤버 추방 테스트
    def test_kick_member_success_by_leader(self) -> None:
        """리더가 멤버를 정상적으로 추방할 수 있다."""
        self.client.force_authenticate(user=self.leader)
        url = reverse(
            "studies:study-member-kick",
            kwargs={"group_uuid": self.group.uuid, "member_id": self.member_member.id},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(GroupMember.objects.filter(id=self.member_member.id).exists())

    def test_kick_member_forbidden_by_non_leader(self) -> None:
        """리더가 아닌 사용자는 추방할 수 없다."""
        self.client.force_authenticate(user=self.member)
        url = reverse(
            "studies:study-member-kick",
            kwargs={"group_uuid": self.group.uuid, "member_id": self.leader_member.id},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kick_member_unauthenticated(self) -> None:
        """비로그인 사용자는 추방 요청 불가"""
        self.client.logout()
        url = reverse(
            "studies:study-member-kick",
            kwargs={"group_uuid": self.group.uuid, "member_id": self.member_member.id},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # REQ-STDY-007: 스터디 그룹 탈퇴 테스트
    def test_member_leave_group_success(self) -> None:
        """일반 멤버는 스터디 그룹에서 정상적으로 탈퇴할 수 있다."""
        self.client.force_authenticate(user=self.member)
        url = reverse("studies:study-member-leave", kwargs={"group_uuid": self.group.uuid})
        response = self.client.delete(url, {"confirm": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(GroupMember.objects.filter(user=self.member, study_group=self.group).exists())

    def test_leader_cannot_leave_group(self) -> None:
        """리더는 위임 없이 스터디 그룹에서 탈퇴할 수 없다."""
        self.client.force_authenticate(user=self.leader)
        url = reverse("studies:study-member-leave", kwargs={"group_uuid": self.group.uuid})
        response = self.client.delete(url, {"confirm": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("리더는 탈퇴할 수 없습니다", response.data["detail"])

    def test_leave_group_unauthenticated(self) -> None:
        """비로그인 사용자는 탈퇴 요청 불가"""
        self.client.logout()
        url = reverse("studies:study-member-leave", kwargs={"group_uuid": self.group.uuid})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # REQ-STDY-008: 스터디 그룹 리더 위임 테스트
    def test_delegate_leader_success(self) -> None:
        """리더가 다른 멤버에게 리더 권한을 위임할 수 있다."""
        self.client.force_authenticate(user=self.leader)
        url = reverse("studies:delegate-leader", kwargs={"group_uuid": self.group.uuid})
        data = {"target_member_id": self.member_member.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_member.refresh_from_db()
        self.leader_member.refresh_from_db()
        self.assertTrue(self.member_member.is_leader)
        self.assertFalse(self.leader_member.is_leader)

    def test_delegate_leader_forbidden_by_non_leader(self) -> None:
        """리더가 아닌 사용자는 리더 위임 요청 불가"""
        self.client.force_authenticate(user=self.member)
        url = reverse("studies:delegate-leader", kwargs={"group_uuid": self.group.uuid})
        data = {"target_member_id": self.leader_member.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delegate_leader_unauthenticated(self) -> None:
        """비로그인 사용자는 리더 위임 요청 불가"""
        self.client.logout()
        url = reverse("studies:delegate-leader", kwargs={"group_uuid": self.group.uuid})
        data = {"target_member_id": self.member_member.id}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
