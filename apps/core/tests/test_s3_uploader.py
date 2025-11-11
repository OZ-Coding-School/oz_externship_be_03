from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

import boto3
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from moto import mock_aws

from apps.core.utils.s3_uploader import S3Uploader


def _make_file(name: str, content_type: str, data: bytes = b"dummy") -> SimpleUploadedFile:
    """테스트용 파일 객체 생성"""
    return SimpleUploadedFile(name=name, content=data, content_type=content_type)


class S3UploaderTests(TestCase):
    """
    Django TestCase + moto.mock_aws
    - S3Uploader 업로드/삭제 및 Presigned URL 생성 검증
    """

    _mock: Optional[Any] = None

    def setUp(self) -> None:
        """테스트용 S3 mock 환경 구성"""
        self._mock = mock_aws()
        self._mock.start()

        self.bucket = "test-bucket"
        self.region = "ap-northeast-2"

        setattr(settings, "AWS_S3_BUCKET_NAME", self.bucket)
        setattr(settings, "AWS_S3_REGION", self.region)
        setattr(settings, "AWS_S3_ACCESS_KEY_ID", "xxx")
        setattr(settings, "AWS_S3_SECRET_ACCESS_KEY", "yyy")

        # mock 시작 후에 클라이언트를 다시 생성
        S3Uploader.s3_client = boto3.client("s3", region_name=self.region)

        # 버킷 생성
        S3Uploader.s3_client.create_bucket(
            Bucket=self.bucket,
            CreateBucketConfiguration={"LocationConstraint": self.region},
        )

        # 속성들 반영
        S3Uploader.BUCKET_NAME = self.bucket
        S3Uploader.REGION_NAME = self.region
        S3Uploader.S3_BASE_URL = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/"

    def tearDown(self) -> None:
        if self._mock is not None:
            self._mock.stop()

    # ---------------------------
    # 업로드 (서버 경유)
    # ---------------------------
    def test_upload_image_success(self) -> None:
        f = _make_file("cover.png", "image/png")
        # 뷰에서 호출되는 벨리데이터 순서 모방
        S3Uploader.validate_file_name(f)
        S3Uploader.validate_file_extension(f)

        url = S3Uploader.upload_file(f, "uploads/test/")
        self.assertTrue(url.startswith(S3Uploader.S3_BASE_URL))

        key = url.replace(S3Uploader.S3_BASE_URL, "")
        head = S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=key)
        self.assertEqual(head["ResponseMetadata"]["HTTPStatusCode"], 200)

    def test_upload_attachment_success(self) -> None:
        f = _make_file("notes.pdf", "application/pdf")
        S3Uploader.validate_file_name(f)
        S3Uploader.validate_file_extension(f)

        url = S3Uploader.upload_file(f, "uploads/test/")
        self.assertTrue(url.startswith(S3Uploader.S3_BASE_URL))

        key = url.replace(S3Uploader.S3_BASE_URL, "")
        head = S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=key)
        self.assertEqual(head["ResponseMetadata"]["HTTPStatusCode"], 200)

    def test_upload_reject_executable_ext(self) -> None:
        """🚫 .exe 확장자 업로드 거부 (뷰단 벨리데이터 호출 모방)"""
        f = _make_file("malware.exe", "application/octet-stream")

        # upload_file() 내부엔 검증이 없으므로, validator 직접 호출
        with self.assertRaises(Exception):
            S3Uploader.validate_file_name(f)
            S3Uploader.validate_file_extension(f)
            # upload_file 호출 시도 (이전 로직과 동일한 최종 트리거)
            S3Uploader.upload_file(f, "uploads/test/")

    # ---------------------------
    # Presigned POST (업로드용)
    # ---------------------------
    def test_generate_presigned_urls_schema_image(self) -> None:
        files: List[Dict[str, str]] = [{"file_name": "cover.jpg", "content_type": "image/jpeg"}]
        result: List[Dict[str, Any]] = S3Uploader.generate_presigned_urls(
            prefix="uploads/studies/groups/",
            files=files,
        )

        # ✅ 출력 추가
        import json

        print("\n[DEBUG] Presigned URL result:\n", json.dumps(result, indent=2, ensure_ascii=False))

        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertIn("url", item)
        self.assertIn("fields", item)
        self.assertIn("file_url", item)
        self.assertTrue(item["file_url"].startswith(S3Uploader.S3_BASE_URL))
        self.assertTrue(item["key"].startswith("uploads/studies/groups/"))

        fields = item["fields"]
        self.assertEqual(fields.get("acl"), "public-read")
        self.assertEqual(fields.get("Content-Type"), "image/jpeg")

    # ---------------------------
    # 삭제 (단건/복수)
    # ---------------------------
    def test_delete_file_and_files(self) -> None:
        """단건 및 복수 삭제 확인"""
        key1 = f"uploads/tmp/{uuid.uuid4().hex}.txt"
        key2 = f"uploads/tmp/{uuid.uuid4().hex}.txt"

        S3Uploader.s3_client.put_object(Bucket=S3Uploader.BUCKET_NAME, Key=key1, Body=b"a")
        S3Uploader.s3_client.put_object(Bucket=S3Uploader.BUCKET_NAME, Key=key2, Body=b"b")

        # 단건 삭제
        S3Uploader.delete_file(key1)
        with self.assertRaises(Exception):
            S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=key1)

        # 복수 삭제
        S3Uploader.delete_files([key2])
        with self.assertRaises(Exception):
            S3Uploader.s3_client.head_object(Bucket=S3Uploader.BUCKET_NAME, Key=key2)
