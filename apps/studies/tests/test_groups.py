from datetime import date, datetime, timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.lecture.models import CrawledLecture
from apps.studies.models.groups import GroupMember, StudyLecture, StudyGroup

User = get_user_model()


class StudyGroupListCreateViewTest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass",
            nickname="testnick",
            name="테스트유저",
            phone_number="01012345678",
            birthday="2000-01-01",
            gender="M",
        )
        self.client.force_authenticate(user=self.user)

        self.lecture1 = CrawledLecture.objects.create(
            uuid="00000000-0000-0000-0000-000000000001",
            title="강의1",
            instructor="강사1",
            average_rating=4.5,
            duration=120,
            difficulty="EASY",
            description="강의1 설명",
            platform="UDEMY",
            original_price=100000,
            discount_price=50000,
            url_link="https://example.com/lecture1",
            thumbnail_img_url="https://example.com/thumbnail1.jpg",
        )
        self.lecture2 = CrawledLecture.objects.create(
            uuid="00000000-0000-0000-0000-000000000002",
            title="강의2",
            instructor="강사2",
            average_rating=4.0,
            duration=90,
            difficulty="NORMAL",
            description="강의2 설명",
            platform="INFLEARN",
            original_price=150000,
            discount_price=80000,
            url_link="https://example.com/lecture2",
            thumbnail_img_url="https://example.com/thumbnail2.jpg",
        )

        self.group = StudyGroup.objects.create(
            uuid="00000000-0000-0000-0000-000000000001",
            name="테스트 스터디",
            introduction="소개글",
            max_headcount=5,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=7),
            status="ONGOING",
        )

        StudyLecture.objects.create(study_group=self.group, lecture=self.lecture1)
        StudyLecture.objects.create(study_group=self.group, lecture=self.lecture2)

        GroupMember.objects.create(study_group=self.group, user=self.user, is_leader=True)

        self.list_create_url = f"/api/v1/studies/groups/"
        self.group1_url = f"/api/v1/studies/groups/{self.group.uuid}/"

    def test_create_study_group(self) -> None:
        """스터디 그룹 생성"""
        data = {
            "uuid": self.group.uuid,
            "name": "테스트 스터디",
            "introduction": "소개글",
            "max_headcount": 5,
            "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "end_at": (timezone.now() + timedelta(days=7)).isoformat(),
            "lectures": [str(self.lecture1.uuid), str(self.lecture2.uuid)],
        }
        response = self.client.post(self.list_create_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # setup에서 만든 group + 위에서 data로 post한 group 포함 총 2개
        self.assertEqual(StudyGroup.objects.count(), 2)
        self.assertEqual(len(response.json()["lectures"]), 2)

    def test_invalid_start_date(self) -> None:
        """시작일이 오늘 이전이면 400 에러 발생"""
        data = {
            "name": "과거 시작 스터디",
            "introduction": "테스트",
            "max_headcount": 5,
            "start_at": (timezone.now() - timedelta(days=1)).isoformat(),  # 과거 날짜
            "end_at": (timezone.now() + timedelta(days=7)).isoformat(),
            "lectures": [str(self.lecture1.uuid)],
        }

        response = self.client.post(self.list_create_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_at", response.json())
        self.assertEqual(response.json()["start_at"][0], "시작일은 오늘 또는 이후여야 합니다.")

    def test_invalid_end_date(self) -> None:
        """종료일이 시작일보다 5일 미만이면 400 에러 발생"""
        start_at = timezone.now() + timedelta(days=1)
        end_at = start_at + timedelta(days=4)  # 5일 미만

        data = {
            "name": "종료일 짧은 스터디",
            "introduction": "테스트",
            "max_headcount": 5,
            "start_at": "2027-11-01",  # 날짜 한참 뒤로 수정
            "end_at": "2028-11-10",  # 동일
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "status": "PENDING",
            "lectures": [str(self.lecture1.uuid)],
        }

        response = self.client.post(self.list_create_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_at", response.json())
        self.assertEqual(response.json()["end_at"][0], "종료일은 시작일보다 5일 이상 이후여야 합니다.")

    def test_required_field_missing(self) -> None:
        """필수 항목이 비어있으면 400 에러 발생"""
        data = {"introduction": "소개글", "lectures": [str(self.lecture1.uuid)]}

        response = self.client.post(self.list_create_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_max_headcount_too_low(self) -> None:
        """max_headcount가 2 미만이면 400 에러 발생"""
        data = {
            "name": "최소 인원 미달 스터디",
            "introduction": "테스트",
            "max_headcount": 1,  # 범위 벗어남
            "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "end_at": (timezone.now() + timedelta(days=7)).isoformat(),
            "lectures": [str(self.lecture1.uuid)],
        }
        response = self.client.post(self.list_create_url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_headcount", response.json())

    def test_max_headcount_too_high(self) -> None:
        """max_headcount가 10 초과이면 400 에러 발생"""
        data = {
            "name": "최대 인원 초과 스터디",
            "introduction": "테스트",
            "max_headcount": 11,  # 범위 벗어남
            "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "end_at": (timezone.now() + timedelta(days=7)).isoformat(),
            "lectures": [str(self.lecture1.uuid)],
        }
        response = self.client.post(self.list_create_url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_headcount", response.json())

    def test_login_required(self) -> None:
        """로그인하지 않은 상태에서 401 확인"""
        self.client.logout()  # 현재 테스트에서만 로그아웃

        data = {
            "name": "로그인 필요 스터디",
            "introduction": "테스트",
            "max_headcount": 5,
            "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "end_at": (timezone.now() + timedelta(days=7)).isoformat(),
            "lectures": [str(self.lecture1.uuid)],
        }

        response = self.client.post(self.list_create_url, data, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_failed_token_authorize(self) -> None:
        """잘못된 토큰으로 요청하면 401 에러 발생"""
        data = {
            "name": "잘못된 토큰 스터디",
            "introduction": "테스트",
            "max_headcount": 5,
            "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "end_at": (timezone.now() + timedelta(days=7)).isoformat(),
            "lectures": [str(self.lecture1.uuid)],
        }

        self.client.logout()  # ✅ 세션 로그아웃
        self.client.credentials()  # ✅ Authorization 헤더 제거

        response = self.client.post(self.list_create_url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.json())

    def test_list_study_groups(self) -> None:
        response = self.client.get(self.list_create_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)

        group_data = response.json()["results"][0]

        self.assertEqual(len(group_data["lectures"]), 2)
        self.assertEqual(group_data["current_headcount"], 1)
        self.assertTrue(group_data["is_leader"])

    def test_list_login_required(self):
        self.client.logout()
        response = self.client.get(self.list_create_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_status_ended(self):
        # 상태 변경
        self.group.status = "ENDED"
        self.group.save()

        response = self.client.get(self.list_create_url + "?status=ENDED")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)  # 필터에 걸림

    def test_filter_status_ended_group_ongoing(self):
        response = self.client.get(self.list_create_url + "?status=ENDED")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 0)


class StudyGroupDetailUpdateViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass",
            nickname="tester",
            name="테스트유저",
            phone_number="01012345678",
            birthday="2000-01-01",
            gender="M",
        )
        self.client.force_authenticate(user=self.user)

        self.lecture1 = CrawledLecture.objects.create(
            title="강의1",
            instructor="강사1",
            average_rating=4.5,
            duration=120,
            difficulty="EASY",
            description="강의1 설명",
            platform="UDEMY",
            original_price=10000,
            discount_price=5000,
            url_link="https://example.com/1",
        )
        self.lecture2 = CrawledLecture.objects.create(
            title="강의2",
            instructor="강사2",
            average_rating=4.0,
            duration=90,
            difficulty="NORMAL",
            description="강의2 설명",
            platform="INFLEARN",
            original_price=20000,
            discount_price=10000,
            url_link="https://example.com/2",
        )

        self.group = StudyGroup.objects.create(
            uuid="00000000-0000-0000-0000-000000000111",
            name="테스트 스터디",
            introduction="소개글",
            max_headcount=5,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=7),
        )

        StudyLecture.objects.create(study_group=self.group, lecture=self.lecture1)
        StudyLecture.objects.create(study_group=self.group, lecture=self.lecture2)

        GroupMember.objects.create(study_group=self.group, user=self.user, is_leader=True)

        self.detail_url = f"/api/v1/studies/groups/{self.group.uuid}/"

    def test_get_study_group_detail(self) -> None:
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["uuid"], str(self.group.uuid))
        self.assertEqual(data["name"], "테스트 스터디")
        self.assertEqual(data["current_headcount"], 1)

        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["nickname"], "tester")

        self.assertEqual(len(data["lectures"]), 2)
        self.assertEqual(data["lectures"][0]["title"], "강의1")

    def test_get_detail_login_required(self) -> None:
        self.client.logout()
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_study_group(self) -> None:
        data = {
            "name": "수정된 스터디",
            "introduction": "변경된 소개글",
            "max_headcount": 7,
            "lectures": [str(self.lecture1.uuid), str(self.lecture2.uuid)],
        }

        response = self.client.put(self.detail_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        updated = StudyGroup.objects.get(uuid=self.group.uuid)
        self.assertEqual(updated.name, "수정된 스터디")
        self.assertEqual(updated.max_headcount, 7)

        self.assertEqual(updated.lectures.count(), 2)

    def test_update_invalid_max_headcount(self) -> None:
        data = {"max_headcount": 1}  # 2 미만 → 오류
        response = self.client.put(self.detail_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_headcount", response.json())

    def test_update_too_many_lectures(self) -> None:
        extra_lectures = [
            CrawledLecture.objects.create(
                title=f"추가강의{i}",
                instructor="강사",
                average_rating=3.0,
                duration=60,
                difficulty="EASY",
                description="desc",
                platform="UDEMY",
                original_price=10000,
                discount_price=5000,
                url_link=f"https://example.com/x{i}",
            )
            for i in range(6)
        ]

        data = {"lectures": [str(l.uuid) for l in extra_lectures]}  # 6개

        response = self.client.put(self.detail_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lectures", response.json())

    def test_update_login_required(self) -> None:
        self.client.logout()

        data = {"name": "로그인 없이 수정"}

        response = self.client.put(self.detail_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_group_not_found(self) -> None:
        wrong_url = "/api/v1/studies/groups/00000000-0000-0000-0000-999999999999/"
        data = {"name": "존재하지 않는 그룹"}

        response = self.client.put(wrong_url, data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


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
