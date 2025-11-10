from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any, Literal, cast
from unittest.mock import patch

import boto3
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from moto import mock_aws
from PIL import Image
from rest_framework import status

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.core.utils.s3_uploader import S3Uploader
from apps.users.enums import Gender, PhoneVerificationPurpose
from apps.users.utils.verify_token import issue_verify_token

User = get_user_model()


class UserProfileUpdateTests(IsolatedRedisTestClient):
    """
    일반 정보 수정 테스트
    """

    def setUp(self) -> None:
        self.url = reverse("users:user_update_profile")

        self.me = User.objects.create_user(
            email="me@example.com",
            password="pw1234!!",
            nickname="me_nick",
            name="나",
            phone_number="01011112222",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="pw1234!!",
            nickname="other_nick",
            name="상대",
            phone_number="01099998888",
            birthday=date(1998, 1, 1),
            gender=Gender.FEMALE,
            is_active=True,
        )

        # 인증
        self.client.force_authenticate(user=self.me)

    def test_auth_required(self) -> None:
        """
        사용자 인증 필요
        """
        self.client.force_authenticate(user=None)
        resp = self.client.patch(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        body = resp.json()
        self.assertIn("detail", body)

    def test_update_nickname_success(self) -> None:
        """
        닉네임만 변경 성공
        """
        payload = {"nickname": "new_nick"}
        response = self.client.patch(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["detail"], "내 정보가 수정되었습니다.")
        self.assertEqual(body["data"]["nickname"], "new_nick")

    def test_nickname_validator_digits_only(self) -> None:
        """
        [Validator] 닉네임: 숫자만 불가
        """
        resp = self.client.patch(self.url, {"nickname": "123456"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nickname", resp.json())

    def test_nickname_validator_regex_fail(self) -> None:
        """
        [Validator] 닉네임: 정규식 불일치(짧거나 특수문자)
        """
        resp = self.client.patch(self.url, {"nickname": "!"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nickname", resp.json())

    def test_nickname_validator_korean_badword(self) -> None:
        """
        [Validator] 닉네임: 한글 금칙어(욕설) 포함
        """
        resp = self.client.patch(self.url, {"nickname": "개새끼킹"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nickname", resp.json())

    @patch("apps.users.validators.predict_prob", return_value=[0.9])
    def test_nickname_validator_english_profane(self, _mock_predict: Any) -> None:
        """
        [Validator] 닉네임: 영어 비속어 확률 경로 (profanity_check) - patch 사용
        """
        resp = self.client.patch(self.url, {"nickname": "verybadword"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nickname", resp.json())

    def test_nickname_validator_valid(self) -> None:
        """
        [Validator] 닉네임: 정상 케이스
        """
        resp = self.client.patch(self.url, {"nickname": "nick_ok_01"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["data"]["nickname"], "nick_ok_01")

    """
    [Validator] 휴대폰 형식 오류 (validate_korean_phone)
    """

    def test_phone_validator_format_error(self) -> None:
        resp = self.client.patch(self.url, {"phone_number": "01112345678"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        body = resp.json()
        self.assertIn("phone_number", body)
        # 에러 메시지 포맷이 프로젝트별로 다를 수 있으므로 키 존재만 체크

    def test_change_phone_missing_token(self) -> None:
        """
        휴대폰 변경: verify_token 누락 -> 400
        """
        resp = self.client.patch(self.url, {"phone_number": "01012345678"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.json())

    def test_change_phone_invalid_token(self) -> None:
        """
        휴대폰 변경: 토큰 불일치/만료 -> 401
        """
        wrong = issue_verify_token(
            sub="01055556666",
            to="me@example.com",
            purpose=PhoneVerificationPurpose.CHANGE_PHONE,
        )
        resp = self.client.patch(self.url, {"phone_number": "01012345678", "phone_verify_token": wrong}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", resp.json())

    def test_change_phone_success_and_token_consumed(self) -> None:
        """
        휴대폰 변경 성공 + 원타임 소비 확인
        """
        new_phone = "01012345678"
        token = issue_verify_token(
            sub=new_phone,
            to="me@example.com",
            purpose=PhoneVerificationPurpose.CHANGE_PHONE,
        )
        # 1차 성공
        resp1 = self.client.patch(self.url, {"phone_number": new_phone, "phone_verify_token": token}, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK, msg=resp1.content)
        self.assertEqual(resp1.json()["data"]["phone_number"], new_phone)
        # 동일 토큰 재사용 → 401
        resp2 = self.client.patch(self.url, {"phone_number": "01077778888", "phone_verify_token": token}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_phone_duplicate_conflict_via_serializer(self) -> None:
        """
        휴대폰 중복 → 409 매핑 확인
        """
        # 바꾸려는 번호로 인증 토큰 발급
        dup_phone = self.other.phone_number
        token = issue_verify_token(
            sub=dup_phone,
            to="me@example.com",
            purpose=PhoneVerificationPurpose.CHANGE_PHONE,
        )

        resp = self.client.patch(
            self.url,
            {"phone_number": dup_phone, "phone_verify_token": token},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, msg=resp.content)
        self.assertIn("error", resp.json())

    def test_change_nickname_duplicate_via_service(self) -> None:
        """
        (서비스) 닉네임 중복 → 400
        """
        resp = self.client.patch(self.url, {"nickname": self.other.nickname}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.json().get("error"), "이미 사용 중인 닉네임입니다.")

    # --- moto S3 helper (이미지 테스트에서만 사용) ---
    _moto: Any = None
    bucket: str
    region: str

    def _start_s3_mock(self) -> None:
        self._moto = mock_aws()
        self._moto.start()

        self.bucket = "test-bucket"
        self.region = "ap-northeast-2"

        # settings 및 moto 클라이언트 준비
        setattr(settings, "AWS_S3_BUCKET_NAME", self.bucket)
        setattr(settings, "AWS_S3_REGION", self.region)
        setattr(settings, "AWS_S3_ACCESS_KEY_ID", "xxx")
        setattr(settings, "AWS_S3_SECRET_ACCESS_KEY", "yyy")

        s3 = boto3.client("s3", region_name=self.region)
        s3.create_bucket(
            Bucket=self.bucket,
            CreateBucketConfiguration={"LocationConstraint": cast(Literal["ap-northeast-2"], self.region)},
        )

        # S3Uploader를 moto 클라이언트로 바인딩
        S3Uploader.BUCKET_NAME = self.bucket
        S3Uploader.REGION_NAME = self.region
        S3Uploader.s3_client = s3
        S3Uploader.S3_BASE_URL = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/"

    def _stop_s3_mock(self) -> None:
        if self._moto:
            self._moto.stop()
            self._moto = None

    # --- (1) 프로필 이미지 업로드 성공 ---
    def test_update_profile_image_only_success(self) -> None:
        """
        프로필 이미지 변경 성공 (닉네임/휴대폰 변경 없음)
        """
        self._start_s3_mock()
        try:
            buf = BytesIO()
            Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")  # 진짜 PNG
            buf.seek(0)

            img = SimpleUploadedFile("avatar.png", buf.getvalue(), content_type="image/png")
            resp = self.client.patch(self.url, {"profile_img": img}, format="multipart")

            self.assertEqual(resp.status_code, status.HTTP_200_OK, msg=resp.content)
            body = resp.json()
            self.assertEqual(body["detail"], "내 정보가 수정되었습니다.")
            new_url = body["data"]["profile_img_url"]
            self.assertTrue(new_url.startswith(S3Uploader.S3_BASE_URL))

            # moto S3에 실제 객체 존재 확인
            new_key = new_url.replace(S3Uploader.S3_BASE_URL, "")
            head = S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=new_key)
            self.assertEqual(head["ResponseMetadata"]["HTTPStatusCode"], 200)
        finally:
            self._stop_s3_mock()

    # --- (2) 기존 이미지가 있을 때 교체 → 기존 이미지 삭제 확인 ---
    def test_update_profile_image_replaces_old(self) -> None:
        """
        기존 이미지가 있을 때 새 이미지로 교체 시, 커밋 후 기존 이미지가 S3에서 삭제된다.
        """
        self._start_s3_mock()
        try:
            buf = BytesIO()
            Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")  # 진짜 PNG
            buf.seek(0)
            img_bytes = buf.getvalue()

            # 기존 이미지 주입 + URL 세팅
            old_key = f"profiles/{self.me.id}/old.png"
            S3Uploader.s3_client.put_object(
                Bucket=S3Uploader.BUCKET_NAME,
                Key=old_key,
                Body=img_bytes,
                ACL="public-read",
            )

            self.me.profile_img_url = S3Uploader.S3_BASE_URL + old_key
            self.me.save(update_fields=["profile_img_url"])

            # 새 이미지 업로드
            buf2 = BytesIO()
            Image.new("RGB", (1, 1), (255, 0, 0)).save(buf2, format="PNG")
            buf2.seek(0)
            new_img = SimpleUploadedFile("avatar2.png", buf2.getvalue(), content_type="image/png")

            resp = self.client.patch(self.url, {"profile_img": new_img}, format="multipart")
            self.assertEqual(resp.status_code, status.HTTP_200_OK, msg=resp.content)

            body = resp.json()
            new_url = body["data"]["profile_img_url"]
            self.assertTrue(new_url.startswith(S3Uploader.S3_BASE_URL))
            new_key = new_url.replace(S3Uploader.S3_BASE_URL, "")

            # 새 객체는 존재
            head_new = S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=new_key)
            self.assertEqual(head_new["ResponseMetadata"]["HTTPStatusCode"], 200)

            # 기존 객체는 삭제되었는지 확인(존재 조회 시 예외)
            with self.assertRaises(Exception):
                S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=old_key)
        finally:
            self._stop_s3_mock()


class ChangePasswordAPITests(IsolatedRedisTestClient):
    def setUp(self) -> None:
        self.url = reverse("users:user_change_password")
        self.user = User.objects.create_user(
            email="user@example.com",
            password="OldPass!234",
            nickname="me_nick",
            name="나",
            phone_number="01011112222",
            birthday=date(1999, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self) -> None:
        """정상 변경 → 200 + detail"""
        payload = {
            "current_password": "OldPass!234",
            "new_password": "New!2345",
            "new_password_confirm": "New!2345",
        }
        resp = self.client.patch(self.url, payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json().get("detail"), "비밀번호가 변경되었습니다.")

        # DB 반영 확인
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New!2345"))
        self.assertFalse(self.user.check_password("OldPass!234"))

    def test_change_password_wrong_current(self) -> None:
        """현재 비밀번호 불일치 → 400"""
        payload = {
            "current_password": "Wrong!234",
            "new_password": "New!2345",
            "new_password_confirm": "New!2345",
        }
        resp = self.client.patch(self.url, payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json().get("error"), "현재 비밀번호가 올바르지 않습니다.")

    def test_change_password_mismatch_confirm(self) -> None:
        """새/확인 불일치 → 400"""
        payload = {
            "current_password": "OldPass!234",
            "new_password": "New!2345",
            "new_password_confirm": "New!2345xxxx",
        }
        resp = self.client.patch(self.url, payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json().get("error"), "새 비밀번호와 확인 비밀번호가 일치하지 않습니다.")

    def test_change_password_same_as_current(self) -> None:
        """새 비밀번호 == 현재 비밀번호 → 400"""
        payload = {
            "current_password": "OldPass!234",
            "new_password": "OldPass!234",
            "new_password_confirm": "OldPass!234",
        }
        resp = self.client.patch(self.url, payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json().get("error"), "새 비밀번호는 이전 비밀번호와 달라야 합니다.")

    def test_change_password_policy_too_short(self) -> None:
        """
        정책 위반(최소 길이) → 400
        - Django validator가 반환하는 첫 메시지를 DRF ValidationError로 변환하는 로직이 제대로 동작해야 함
        - 예시 메시지(ko 번역 기준): "이 비밀번호는 너무 짧습니다. 최소 8자 이상이어야 합니다."
        """
        payload = {
            "current_password": "OldPass!234",
            "new_password": "Aa1!",  # 4자: 길이 위반 유도
            "new_password_confirm": "Aa1!",
        }
        resp = self.client.patch(self.url, payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # 문자열만 내려오는지(리스트 to string 아님) 확인
        err = resp.json().get("error")
        self.assertIsInstance(err, str)
        self.assertTrue("최소 8자" in err or "짧" in err)

    def test_change_password_unauthorized(self) -> None:
        """인증 누락 → 401"""
        # 인증 해제
        self.client.force_authenticate(user=None)

        payload = {
            "current_password": "OldPass!234",
            "new_password": "New!2345",
            "new_password_confirm": "New!2345",
        }
        resp = self.client.patch(self.url, payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        # DRF 기본 메시지로 내려올 수 있으므로 키 존재만 확인
        self.assertIn("detail", resp.json())
