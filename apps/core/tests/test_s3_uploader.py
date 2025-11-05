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
    return SimpleUploadedFile(name=name, content=data, content_type=content_type)


class S3UploaderTests(TestCase):
    """
    Django TestCase + moto.mock_aws
    - setUp/tearDown에서 moto S3 구성
    - S3Uploader 클래스 변수 재바인딩 (버킷/리전/클라이언트/BASE_URL)
    - 업로드(이미지/파일), Presigned POST 스키마, 단건/복수 삭제 검증
    """

    _mock: Optional[Any] = None

    def setUp(self) -> None:
        # 1) moto 시작
        self._mock = mock_aws()
        self._mock.start()

        # 2) 테스트 설정
        self.bucket: str = "test-bucket"
        self.region: Literal["ap-northeast-2"] = "ap-northeast-2"

        # settings 주입
        setattr(settings, "AWS_S3_BUCKET_NAME", self.bucket)
        setattr(settings, "AWS_S3_REGION", self.region)
        setattr(settings, "AWS_S3_ACCESS_KEY_ID", "xxx")
        setattr(settings, "AWS_S3_SECRET_ACCESS_KEY", "yyy")

        # 3) moto 클라이언트/버킷 생성
        client = boto3.client("s3", region_name=self.region)
        client.create_bucket(
            Bucket=self.bucket,
            CreateBucketConfiguration={"LocationConstraint": self.region},
        )

        # 4) S3Uploader 클래스 변수 재바인딩
        S3Uploader.BUCKET_NAME = self.bucket
        S3Uploader.REGION_NAME = self.region
        S3Uploader.s3_client = client
        S3Uploader.S3_BASE_URL = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/"

    def tearDown(self) -> None:
        if self._mock is not None:
            self._mock.stop()

    # ---------------------------
    # 업로드 (서버 경유)
    # ---------------------------
    def test_upload_image_success(self) -> None:
        f = _make_file("cover.png", "image/png")
        url = S3Uploader.upload_file(f, "uploads/test/")
        self.assertTrue(url.startswith(S3Uploader.S3_BASE_URL))

        key = url.replace(S3Uploader.S3_BASE_URL, "")
        head = S3Uploader.s3_client.head_object(
            Bucket=S3Uploader.BUCKET_NAME,
            Key=key,
        )
        self.assertEqual(head["ResponseMetadata"]["HTTPStatusCode"], 200)

    def test_upload_attachment_success(self) -> None:
        f = _make_file("notes.pdf", "application/pdf")
        url = S3Uploader.upload_file(f, "uploads/test/")

        self.assertTrue(url.startswith(S3Uploader.S3_BASE_URL))

        key = url.replace(S3Uploader.S3_BASE_URL, "")
        head = S3Uploader.s3_client.head_object(
            Bucket=S3Uploader.BUCKET_NAME,
            Key=key,
        )
        self.assertEqual(head["ResponseMetadata"]["HTTPStatusCode"], 200)

    def test_upload_reject_executable_ext(self) -> None:
        f = _make_file("malware.exe", "application/octet-stream")
        with self.assertRaises(Exception):
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
        key1 = f"uploads/tmp/{uuid.uuid4().hex}.txt"
        key2 = f"uploads/tmp/{uuid.uuid4().hex}.txt"

        # 사전 객체 생성
        S3Uploader.s3_client.put_object(Bucket=S3Uploader.BUCKET_NAME, Key=key1, Body=b"a")
        S3Uploader.s3_client.put_object(Bucket=S3Uploader.BUCKET_NAME, Key=key2, Body=b"b")

        # 단건 삭제
        S3Uploader.delete_file(key1)
        with self.assertRaises(Exception):
            S3Uploader.s3_client.head_object(
                Bucket=S3Uploader.BUCKET_NAME,
                Key=key1,
            )

        # 복수 삭제
        S3Uploader.delete_files([key2])
        with self.assertRaises(Exception):
            S3Uploader.s3_client.head_object(
                Bucket=S3Uploader.BUCKET_NAME,
                Key=key2,
            )
