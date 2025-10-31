from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.users.enums import UserStatus
from apps.users.models import User, Withdrawal


class TestAdminUserAPI(APITestCase):
    """관리자 전용 회원 관리 API 테스트"""

    admin: User
    user: User
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트용 기본 데이터 생성"""
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
        """요청 전 기본 관리자 인증"""
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    # ✅ 회원 목록 조회
    def test_user_list(self) -> None:
        url = reverse("admin_users:admin-user-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        users = response.data["data"]["users"]
        self.assertTrue(len(users) > 0)
        self.assertIn("email", users[0])

    # ✅ 회원 상세 조회 / 수정 / 삭제
    def test_user_detail_update_delete(self) -> None:
        url = reverse("admin_users:admin-user-detail", args=[self.user.id])

        # 상세 조회
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["email"], self.user.email)

        # 정보 수정
        payload_name = {"name": "수정된유저"}
        response = self.client.patch(url, payload_name, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "수정된유저")

        # 삭제
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # 🚫 스태프는 권한 변경 불가
    def test_change_user_role_superuser_only(self) -> None:
        target = User.objects.create_user(
            email="target@example.com",
            password="1234",
            name="일반유저",
            nickname="target",
            phone_number="01055556666",
            gender="female",
            birthday="1995-05-05",
        )

        staff = User.objects.create_user(
            email="staff@example.com",
            password="1234",
            name="스태프유저",
            nickname="staff",
            phone_number="01033334444",
            gender="male",
            birthday="1991-03-03",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff)

        url = reverse("admin_users:admin-user-role-update", args=[target.id])
        payload = {"role": "admin"}
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        target.refresh_from_db()
        self.assertFalse(target.is_superuser)
        self.assertFalse(target.is_staff)

    # ✅ 탈퇴 예정 상태 필드 확인
    def test_user_status_field(self) -> None:
        Withdrawal.objects.create(user=self.user, due_date=timezone.now())
        url = reverse("admin_users:admin-user-detail", args=[self.user.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("is_active", data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], UserStatus.WITHDRAWAL_PENDING.value)

    # ⚠️ 예외 케이스 - 존재하지 않는 유저 상세조회
    def test_user_detail_not_found(self) -> None:
        url = reverse("admin_users:admin-user-detail", args=[999999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("회원 정보를 찾을 수 없습니다.", response.data["error"])

    # ⚠️ 예외 케이스 - 존재하지 않는 유저 삭제
    def test_delete_user_not_found(self) -> None:
        url = reverse("admin_users:admin-user-detail", args=[999999])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ⚠️ 예외 케이스 - 잘못된 role 입력
    def test_change_user_role_invalid_role(self) -> None:
        url = reverse("admin_users:admin-user-role-update", args=[self.user.id])
        payload = {"role": "INVALID_ROLE"}
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
