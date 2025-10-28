from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.test import TestCase
from django.utils import timezone

from apps.users.enums import Role, UserStatus
from apps.users.models import User, Withdrawal
from apps.users.services.admin_users_services import AdminUserService


class AdminUserServiceTest(TestCase):
    """AdminUserService 단위 테스트 (비즈니스 로직 검증)"""

    admin: User
    user: User

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트용 유저 데이터 세팅"""
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

    # ✅ 정상 케이스 -------------------------
    def test_get_user_list(self) -> None:
        """전체 유저 목록 조회"""
        result = AdminUserService.get_user_list()
        self.assertIn(self.admin, result)
        self.assertIn(self.user, result)

    def test_get_user_detail(self) -> None:
        """단일 유저 상세 조회"""
        result = AdminUserService.get_user_detail(self.user.id)
        self.assertEqual(result.email, self.user.email)

    def test_update_user_info(self) -> None:
        """유저 정보 수정"""
        data: dict[str, str] = {"name": "Updated Name"}
        updated = AdminUserService.update_user_info(self.user.id, data)
        self.assertEqual(updated.name, "Updated Name")

    def test_change_user_role_admin(self) -> None:
        """권한 변경: ADMIN"""
        updated = AdminUserService.change_user_role(self.user.id, Role.ADMIN.value)
        self.assertTrue(updated.is_superuser)
        self.assertTrue(updated.is_staff)

    def test_change_user_role_staff(self) -> None:
        """권한 변경: STAFF"""
        updated = AdminUserService.change_user_role(self.user.id, Role.STAFF.value)
        self.assertFalse(updated.is_superuser)
        self.assertTrue(updated.is_staff)

    def test_change_user_role_user(self) -> None:
        """권한 변경: USER"""
        updated = AdminUserService.change_user_role(self.user.id, Role.USER.value)
        self.assertFalse(updated.is_superuser)
        self.assertFalse(updated.is_staff)

    def test_get_user_status_active(self) -> None:
        """활성 상태"""
        self.user.is_active = True
        self.user.save()
        status = AdminUserService.get_user_status(self.user)
        self.assertEqual(status, UserStatus.ACTIVE)

    def test_get_user_status_withdrawal_pending(self) -> None:
        """탈퇴 예정 상태"""
        Withdrawal.objects.create(user=self.user, due_date=timezone.now())
        status = AdminUserService.get_user_status(self.user)
        self.assertEqual(status, UserStatus.WITHDRAWAL_PENDING)

    def test_get_user_status_inactive(self) -> None:
        """비활성 상태"""
        self.user.is_active = False
        self.user.save()
        status = AdminUserService.get_user_status(self.user)
        self.assertEqual(status, UserStatus.INACTIVE)

    # ⚠️ 예외 케이스 -------------------------
    def test_get_user_detail_not_found(self) -> None:
        """존재하지 않는 유저 조회 시 예외 발생"""
        with self.assertRaises(Exception):
            AdminUserService.get_user_detail(999999)

    def test_update_user_info_invalid_field(self) -> None:
        """존재하지 않는 필드 수정 시 무시"""
        data: dict[str, str] = {"nonexistent_field": "test"}
        updated = AdminUserService.update_user_info(self.user.id, data)
        # unknown 필드는 무시되지만 user 인스턴스는 반환됨
        self.assertTrue(hasattr(updated, "email"))

    def test_change_user_role_invalid(self) -> None:
        """잘못된 권한 입력 시 ValueError 발생"""
        with self.assertRaises(ValueError):
            AdminUserService.change_user_role(self.user.id, "INVALID_ROLE")

    def test_delete_user_not_found(self) -> None:
        """존재하지 않는 유저 삭제 시 예외 발생"""
        with self.assertRaises(Exception):
            AdminUserService.delete_user(999999)