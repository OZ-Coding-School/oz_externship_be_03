from __future__ import annotations

from io import BytesIO
from typing import Literal, Mapping, Optional, Protocol, Union
from unittest.mock import patch

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from moto import mock_aws
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.exceptions import Conflict
from apps.core.utils.s3_uploader import S3Uploader
from apps.users.enums import Role, UserStatus
from apps.users.models import User, Withdrawal
from apps.users.services.admin_users_services import AdminUserService


class AdminUserSeedMixin:
    """어드민/스태프/일반/검색/삭제/탈퇴예정 등 테스트 공통 데이터"""

    # 뷰 테스트 핸들
    admin: User
    user: User
    staff: User
    staff2: User
    non_staff: User
    role_target: User
    delete_target: User
    alice: User

    # 서비스 테스트 핸들
    user_active: User
    user_inactive: User
    staff_user: User
    normal_user2: User
    withdraw_user: User

    @classmethod
    def setUpTestData(cls) -> None:
        # --- 기본 관리자/일반 ---
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

        # --- 목록/권한/삭제/검색 계정 ---
        User.objects.bulk_create(
            [
                User(
                    email="staff@example.com",
                    name="스태프유저",
                    nickname="staff",
                    phone_number="01033334444",
                    gender="male",
                    birthday="1991-03-03",
                    is_staff=True,
                    is_active=True,
                ),
                User(
                    email="staff2@example.com",
                    name="스태프2",
                    nickname="staff2",
                    phone_number="01099990000",
                    gender="male",
                    birthday="1991-03-03",
                    is_staff=True,
                    is_active=True,
                ),
                User(
                    email="nonstaff@example.com",
                    name="일반",
                    nickname="nonstaff",
                    phone_number="01022223333",
                    gender="male",
                    birthday="1994-04-04",
                    is_active=True,
                ),
                User(
                    email="role-target@example.com",
                    name="권한대상",
                    nickname="role_tgt",
                    phone_number="01012121212",
                    gender="female",
                    birthday="1996-06-06",
                    is_active=True,
                ),
                User(
                    email="delete-me@example.com",
                    name="삭제대상",
                    nickname="deleteme",
                    phone_number="01023232323",
                    gender="male",
                    birthday="1997-07-07",
                    is_active=True,
                ),
                User(
                    email="alice@example.com",
                    name="앨리스",
                    nickname="alice",
                    phone_number="01077778888",
                    gender="female",
                    birthday="1993-03-03",
                    is_active=True,
                ),
            ]
        )

        # 뷰 테스트 참조 핸들
        cls.staff = User.objects.get(email="staff@example.com")
        cls.staff2 = User.objects.get(email="staff2@example.com")
        cls.non_staff = User.objects.get(email="nonstaff@example.com")
        cls.role_target = User.objects.get(email="role-target@example.com")
        cls.delete_target = User.objects.get(email="delete-me@example.com")
        cls.alice = User.objects.get(email="alice@example.com")

        # --- 서비스 로직 검증용 개별 계정 ---
        cls.user_active = User.objects.create_user(
            email="active@example.com",
            password="1234",
            name="액티브",
            nickname="active",
            phone_number="01011113333",
            gender="female",
            birthday="1992-02-02",
            is_active=True,
        )
        cls.user_inactive = User.objects.create_user(
            email="inactive@example.com",
            password="1234",
            name="비활성",
            nickname="inactive",
            phone_number="01022224444",
            gender="male",
            birthday="1993-03-03",
            is_active=False,
        )
        cls.staff_user = User.objects.create_user(
            email="staff-service@example.com",
            password="1234",
            name="스태프",
            nickname="staffsvc",
            phone_number="01033335555",
            gender="male",
            birthday="1994-04-04",
            is_staff=True,
        )
        cls.normal_user2 = User.objects.create_user(
            email="user2@example.com",
            password="1234",
            name="일반2",
            nickname="user2",
            phone_number="01044446666",
            gender="female",
            birthday="1995-05-05",
        )
        cls.withdraw_user = User.objects.create_user(
            email="withdraw@example.com",
            password="1234",
            name="탈퇴예정",
            nickname="withdraw",
            phone_number="01055557777",
            gender="female",
            birthday="1996-06-06",
            is_active=True,
        )
        Withdrawal.objects.create(user=cls.withdraw_user, due_date=timezone.now())


# ---------------------------------------------------------------------
# 어드민 뷰 테스트
# ---------------------------------------------------------------------
@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class TestAdminUserViewAPI(AdminUserSeedMixin, APITestCase):
    """관리자 전용 회원 관리 API 테스트"""

    def setUp(self) -> None:
        """요청 전 기본 관리자 인증"""
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    # ========== S3 moto 헬퍼 ==========
    class _MotoLike(Protocol):
        def start(self) -> None: ...
        def stop(self) -> None: ...

    _moto: Optional[_MotoLike] = None
    _s3: Optional[BaseClient] = None
    _s3_bucket: str = "test-bucket"
    _s3_region: Literal["ap-northeast-2"] = "ap-northeast-2"

    def _start_s3_mock(self) -> None:
        self._moto = mock_aws()
        self._moto.start()

        setattr(settings, "AWS_S3_BUCKET_NAME", self._s3_bucket)
        setattr(settings, "AWS_S3_REGION", self._s_region if hasattr(self, "_s_region") else self._s3_region)
        setattr(settings, "AWS_S3_ACCESS_KEY_ID", "xxx")
        setattr(settings, "AWS_S3_SECRET_ACCESS_KEY", "yyy")

        # moto S3 클라이언트
        self._s3 = boto3.client("s3", region_name=self._s3_region)
        self._s3.create_bucket(
            Bucket=self._s3_bucket,
            CreateBucketConfiguration={"LocationConstraint": self._s3_region},
        )

        # S3Uploader 바인딩
        S3Uploader.BUCKET_NAME = self._s3_bucket
        S3Uploader.REGION_NAME = self._s3_region
        S3Uploader.s3_client = self._s3
        S3Uploader.S3_BASE_URL = f"https://{self._s3_bucket}.s3.{self._s3_region}.amazonaws.com/"

    def _stop_s3_mock(self) -> None:
        if self._moto:
            self._moto.stop()
            self._moto = None
            self._s3 = None

    # ✅ 회원 목록 조회
    def test_user_list(self) -> None:
        url = reverse("users:admin-user-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        users = response.data["data"]["users"]
        self.assertTrue(len(users) > 0)
        self.assertIn("email", users[0])

    # ✅ 회원 상세 조회 / 수정 / 삭제
    def test_user_detail_update_delete(self) -> None:
        url = reverse("users:admin-user-detail", args=[self.user.id])

        # 상세 조회
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["email"], self.user.email)

        # 정보 수정
        payload_name = {"name": "수정된유저"}
        response = self.client.patch(url, payload_name, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "수정된유저")

        # 삭제 (200 + 본문)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(id=self.user.id)

    # 🚫 스태프는 권한 변경 불가
    def test_change_user_role_superuser_only(self) -> None:
        self.client.force_authenticate(user=self.staff)
        url = reverse("users:admin-user-role-update", args=[self.role_target.id])
        response = self.client.patch(url, {"role": "admin"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.role_target.refresh_from_db()
        self.assertFalse(self.role_target.is_superuser)
        self.assertFalse(self.role_target.is_staff)

    # ✅ 탈퇴 예정 상태 필드 확인
    def test_user_status_field(self) -> None:
        Withdrawal.objects.create(user=self.user, due_date=timezone.now())
        url = reverse("users:admin-user-detail", args=[self.user.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("status", data)
        self.assertEqual(data["status"], UserStatus.WITHDRAWAL_PENDING.value)

    # ⚠️ 존재하지 않는 유저 상세조회
    def test_user_detail_not_found(self) -> None:
        url = reverse("users:admin-user-detail", args=[999_999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("회원 정보를 찾을 수 없습니다.", response.data["error"])

    # ⚠️ 존재하지 않는 유저 삭제
    def test_delete_user_not_found(self) -> None:
        url = reverse("users:admin-user-detail", args=[999_999])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ⚠️ 잘못된 role 입력
    def test_change_user_role_invalid_role(self) -> None:
        url = reverse("users:admin-user-role-update", args=[self.admin.id])
        response = self.client.patch(url, {"role": "INVALID_ROLE"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 목록: 페이지네이션/검색/필터/정렬 커버
    def test_user_list_with_query_params(self) -> None:
        url = reverse("users:admin-user-list")
        params: Mapping[str, Union[str, int]] = {
            "page": 1,
            "limit": 20,
            "q": "alice",
            "role": "user",
            "status": "active",
            "order": "-id",
        }
        resp = self.client.get(url, params)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.data["data"]
        self.assertIn("users", body)
        self.assertIn("pagination", body)
        self.assertIn("page", body["pagination"])
        self.assertIn("limit", body["pagination"])
        emails = [u["email"] for u in body["users"]]
        self.assertTrue(any("alice@" in e for e in emails))

    # 권한: 비스태프는 상세/수정 403
    def test_permission_forbidden_for_non_staff_on_get_and_patch(self) -> None:
        self.client.force_authenticate(user=self.non_staff)
        detail_url = reverse("users:admin-user-detail", args=[self.admin.id])
        r1 = self.client.get(detail_url)
        r2 = self.client.patch(detail_url, {"name": "변경불가"}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

    # 권한: 스태프는 삭제 불가(DELETE 403)
    def test_permission_forbidden_for_staff_on_delete(self) -> None:
        self.client.force_authenticate(user=self.staff2)
        detail_url = reverse("users:admin-user-detail", args=[self.admin.id])
        r = self.client.delete(detail_url)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    # 권한변경: 슈퍼유저 성공(200)
    def test_change_user_role_success_by_superuser(self) -> None:
        url = reverse("users:admin-user-role-update", args=[self.role_target.id])
        r = self.client.patch(url, {"role": "staff"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("detail", r.data)
        self.role_target.refresh_from_db()
        self.assertTrue(self.role_target.is_staff)

    # 권한변경: 대상 없음(404)
    def test_change_user_role_target_not_found(self) -> None:
        url = reverse("users:admin-user-role-update", args=[999_999])
        r = self.client.patch(url, {"role": "user"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    # 삭제: 성공 200 + 메시지 본문 확인
    def test_delete_user_success_returns_200_with_body(self) -> None:
        url = reverse("users:admin-user-detail", args=[self.delete_target.id])
        r = self.client.delete(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("detail", r.data)
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(id=self.delete_target.id)

    # 목록: 기본값 동작(파라미터 없이도 200, 메타 존재)
    def test_user_list_without_params_default_ok(self) -> None:
        url = reverse("users:admin-user-list")
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("pagination", r.data["data"])

    # get_permissions() 미구현 메서드 분기(405)
    def test_permissions_default_branch_on_unsupported_method(self) -> None:
        url = reverse("users:admin-user-detail", args=[self.user.id])
        resp = self.client.put(url, {"name": "nope"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ========== (이미지) 프로필 업로드 성공 ==========
    def test_update_profile_image_only_success(self) -> None:
        self._start_s3_mock()
        try:
            url = reverse("users:admin-user-detail", args=[self.user.id])

            buf = BytesIO()
            Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
            buf.seek(0)
            img = SimpleUploadedFile("avatar.png", buf.getvalue(), content_type="image/png")

            resp = self.client.patch(url, {"profile_img": img}, format="multipart")
            self.assertEqual(resp.status_code, status.HTTP_200_OK, msg=resp.content)

            body = resp.json()
            self.assertIn("detail", body)
            new_url = body["data"]["profile_img_url"]
            self.assertTrue(new_url.startswith(S3Uploader.S3_BASE_URL))

            new_key = new_url.replace(S3Uploader.S3_BASE_URL, "")
            head = S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=new_key)
            self.assertEqual(head["ResponseMetadata"]["HTTPStatusCode"], 200)
        finally:
            self._stop_s3_mock()

    # ========== (이미지) 기존 이미지가 있을 때 교체 → 기존 삭제 ==========
    def test_update_profile_image_replaces_old(self) -> None:
        self._start_s3_mock()
        try:
            url = reverse("users:admin-user-detail", args=[self.user.id])

            buf = BytesIO()
            Image.new("RGB", (1, 1), (0, 255, 0)).save(buf, format="PNG")
            buf.seek(0)
            img_bytes = buf.getvalue()

            old_key = f"profiles/{self.user.id}/old.png"
            S3Uploader.s3_client.put_object(
                Bucket=S3Uploader.BUCKET_NAME,
                Key=old_key,
                Body=img_bytes,
                ACL="public-read",
            )
            self.user.profile_img_url = S3Uploader.S3_BASE_URL + old_key
            self.user.save(update_fields=["profile_img_url"])

            # 새 이미지 업로드
            buf2 = BytesIO()
            Image.new("RGB", (1, 1), (0, 0, 255)).save(buf2, format="PNG")
            buf2.seek(0)
            new_img = SimpleUploadedFile("avatar2.png", buf2.getvalue(), content_type="image/png")

            resp = self.client.patch(url, {"profile_img": new_img}, format="multipart")
            self.assertEqual(resp.status_code, status.HTTP_200_OK, msg=resp.content)

            body = resp.json()
            new_url = body["data"]["profile_img_url"]
            self.assertTrue(new_url.startswith(S3Uploader.S3_BASE_URL))
            new_key = new_url.replace(S3Uploader.S3_BASE_URL, "")

            head_new = S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=new_key)
            self.assertEqual(head_new["ResponseMetadata"]["HTTPStatusCode"], 200)

        finally:
            self._stop_s3_mock()


# ---------------------------------------------------------------------
# 어드민 서비스 테스트
# ---------------------------------------------------------------------
@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AdminUserServiceTest(AdminUserSeedMixin, TestCase):
    # --------------------- 기본/조회 --------------------- #
    def test_get_user(self) -> None:
        u = AdminUserService.get_user(self.user_active.id)
        self.assertEqual(u.email, "active@example.com")

    def test_get_user_not_found(self) -> None:
        with self.assertRaises(Http404):
            AdminUserService.get_user(999_999)

    def test_get_user_list_all(self) -> None:
        qs = AdminUserService.get_user_list()
        emails = set(qs.values_list("email", flat=True))
        self.assertIn("admin@example.com", emails)
        self.assertIn("active@example.com", emails)
        self.assertIn("inactive@example.com", emails)

    def test_get_user_list_search_q_and_order(self) -> None:
        qs = AdminUserService.get_user_list(q="user2", order="-id")
        self.assertTrue(qs.exists())
        user = qs.get(email="user2@example.com")
        self.assertEqual(user.email, "user2@example.com")

    def test_get_user_list_role_filter(self) -> None:
        qs_admin = AdminUserService.get_user_list(role=Role.ADMIN.value)
        self.assertIn(self.admin.id, qs_admin.values_list("id", flat=True))
        qs_staff = AdminUserService.get_user_list(role=Role.STAFF.value)
        self.assertIn(self.staff_user.id, qs_staff.values_list("id", flat=True))
        qs_user = AdminUserService.get_user_list(role=Role.USER.value)
        self.assertIn(self.user_active.id, qs_user.values_list("id", flat=True))

    def test_get_user_list_status_filter(self) -> None:
        qs_active = AdminUserService.get_user_list(status=UserStatus.ACTIVE.value)
        self.assertIn(self.user_active.id, qs_active.values_list("id", flat=True))

        qs_inactive = AdminUserService.get_user_list(status=UserStatus.INACTIVE.value)
        self.assertIn(self.user_inactive.id, qs_inactive.values_list("id", flat=True))

        # 서비스 구현: 탈퇴예정 = is_active=False + Withdrawal 존재
        self.withdraw_user.is_active = False
        self.withdraw_user.save(update_fields=["is_active"])
        qs_withdraw = AdminUserService.get_user_list(status=UserStatus.WITHDRAWAL_PENDING.value)
        self.assertIn(self.withdraw_user.id, qs_withdraw.values_list("id", flat=True))

    # --------------------- 상태/권한 계산 --------------------- #
    def test_get_user_status_active(self) -> None:
        self.user_active.is_active = True
        self.user_active.save(update_fields=["is_active"])
        s = AdminUserService.get_user_status(self.user_active)
        self.assertEqual(s, UserStatus.ACTIVE.value)

    def test_get_user_status_inactive(self) -> None:
        self.user_inactive.is_active = False
        self.user_inactive.save(update_fields=["is_active"])
        s = AdminUserService.get_user_status(self.user_inactive)
        self.assertEqual(s, UserStatus.INACTIVE.value)

    def test_get_user_status_withdrawal_pending(self) -> None:
        self.withdraw_user.is_active = False
        self.withdraw_user.save(update_fields=["is_active"])
        s = AdminUserService.get_user_status(self.withdraw_user)
        self.assertEqual(s, UserStatus.WITHDRAWAL_PENDING.value)

    def test_get_user_role(self) -> None:
        self.assertEqual(AdminUserService.get_user_role(self.admin), Role.ADMIN.value)
        self.assertEqual(AdminUserService.get_user_role(self.staff_user), Role.STAFF.value)
        self.assertEqual(AdminUserService.get_user_role(self.user_active), Role.USER.value)

    # --------------------- 업데이트 --------------------- #
    def test_update_user_info_success(self) -> None:
        u = AdminUserService.get_user(self.user_active.id)
        updated = AdminUserService.update_user_info(u, {"name": "업데이트됨", "nickname": "active_1"})
        self.assertEqual(updated.name, "업데이트됨")
        self.assertEqual(updated.nickname, "active_1")

    def test_update_user_info_no_changes_skip_save(self) -> None:
        u = AdminUserService.get_user(self.user_active.id)
        payload = {"name": u.name, "nickname": u.nickname}
        with patch.object(User, "save", wraps=u.save) as mocked_save:
            _ = AdminUserService.update_user_info(u, payload)
            mocked_save.assert_not_called()

    def test_update_user_info_conflict_nickname(self) -> None:
        other = self.normal_user2
        u = AdminUserService.get_user(self.user_active.id)
        with self.assertRaises(Conflict):
            AdminUserService.update_user_info(u, {"nickname": other.nickname})

    def test_update_user_info_conflict_phone(self) -> None:
        other = self.normal_user2
        u = AdminUserService.get_user(self.user_active.id)
        with self.assertRaises(Conflict):
            AdminUserService.update_user_info(u, {"phone_number": other.phone_number})

    def test_update_user_info_ignore_invalid_field(self) -> None:
        u = AdminUserService.get_user(self.user_active.id)
        updated = AdminUserService.update_user_info(u, {"__nope__": "x"})
        self.assertEqual(updated.id, u.id)

    # --------------------- 권한 변경 --------------------- #
    def test_change_user_role_admin(self) -> None:
        u = AdminUserService.get_user(self.user_active.id)
        changed = AdminUserService.change_user_role(u, Role.ADMIN.value)
        self.assertTrue(changed.is_superuser)
        self.assertTrue(changed.is_staff)

    def test_change_user_role_staff(self) -> None:
        u = AdminUserService.get_user(self.user_active.id)
        changed = AdminUserService.change_user_role(u, Role.STAFF.value)
        self.assertFalse(changed.is_superuser)
        self.assertTrue(changed.is_staff)

    def test_change_user_role_user(self) -> None:
        u = AdminUserService.get_user(self.staff_user.id)
        changed = AdminUserService.change_user_role(u, Role.USER.value)
        self.assertFalse(changed.is_superuser)
        self.assertFalse(changed.is_staff)

    def test_change_user_role_invalid_raises(self) -> None:
        u = AdminUserService.get_user(self.user_active.id)
        with self.assertRaises(ValueError):
            AdminUserService.change_user_role(u, "INVALID")

    def test_change_user_role_noop_skips_save(self) -> None:
        u = AdminUserService.get_user(self.staff_user.id)
        with patch.object(User, "save", wraps=u.save) as mocked_save:
            _ = AdminUserService.change_user_role(u, Role.STAFF.value)
            mocked_save.assert_not_called()

    # --------------------- 삭제 --------------------- #
    def test_delete_user(self) -> None:
        u = User.objects.create_user(
            email="tempdel@example.com",
            password="1234",
            name="삭제대상",
            nickname="tempdel",
            phone_number="01088889999",
            gender="male",
            birthday="1997-07-07",
        )
        AdminUserService.delete_user(u)
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(id=u.id)
