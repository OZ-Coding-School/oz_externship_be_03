from __future__ import annotations

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.users.enums import UserStatus
from apps.users.models import User, Withdrawal


class TestAdminUserAPI(APITestCase):

    admin: User
    user: User
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트용 유저 생성"""
        cls.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="1234",
            name="관리자",
            nickname="admin",
            phone_number="01000000000",
            gender="male",
            birthday="1990-01-01",
        )
        cls.user = User.objects.create_user(
            email="user@example.com",
            password="1234",
            name="일반유저",
            nickname="user",
            phone_number="01011112222",
            gender="female",
            birthday="1992-02-02",
        )

    def setUp(self) -> None:
        """각 테스트 시작 전마다 인증된 관리자 클라이언트 준비"""
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    # ✅ 유저 목록 조회
    def test_user_list(self) -> None:
        url = reverse("users:admin-user-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("email", response.data[0])

    # ✅ 유저 상세 조회
    def test_user_detail(self) -> None:
        url = reverse("users:admin-user-detail", args=[self.user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    # ✅ 유저 정보 수정
    def test_update_user_info(self) -> None:
        url = reverse("users:admin-user-update", args=[self.user.id])
        payload: dict[str, str] = {"name": "수정된유저"}
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "수정된유저")

    # ✅ 유저 권한 변경
    def test_change_user_role(self) -> None:
        url = reverse("users:admin-user-role-update", args=[self.user.id])
        payload: dict[str, str] = {"role": "staff"}  # 소문자 입력 (serializer에서 lower 처리)
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

    # ✅ 유저 삭제
    def test_delete_user(self) -> None:
        url = reverse("users:admin-user-delete", args=[self.user.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # ✅ 유저 상태 필드 (탈퇴 예정)
    def test_user_status_field(self) -> None:
        Withdrawal.objects.create(user=self.user, due_date=timezone.now())
        url = reverse("users:admin-user-detail", args=[self.user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], UserStatus.WITHDRAWAL_PENDING.value)

    # 🚫 스태프 권한으로 삭제 시도 (권한 없음)
    def test_staff_cannot_delete_user(self) -> None:
        """스태프 권한 사용자가 회원 삭제 시 403 Forbidden 응답"""
        staff_user = User.objects.create_user(
            email="staff@example.com",
            password="1234",
            name="스태프유저",
            nickname="staff",
            phone_number="01033334444",
            gender="male",
            birthday="1991-03-03",
            is_staff=True,
        )

        target_user = User.objects.create_user(
            email="target@example.com",
            password="1234",
            name="삭제대상",
            nickname="target",
            phone_number="01044445555",
            gender="female",
            birthday="1995-05-05",
        )

        # 스태프 계정으로 로그인 후 삭제 시도
        self.client.force_authenticate(user=staff_user)
        url = reverse("users:admin-user-delete", args=[target_user.id])
        response = self.client.delete(url)

        # ✅ IsAdminUser permission → superuser만 허용 → 403 반환
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
