# core/utils/s3_uploader.py
"""
공통 S3 Presigned URL 유틸리티 모듈
- boto3 클라이언트 생성
- Presigned URL 생성
- 파일 검증 (별도 validator와 연계)
- 필요 시 S3 객체 삭제 함수 제공
"""

from __future__ import annotations

import uuid
import boto3
from typing import Any

from django.conf import settings


def get_s3_client() -> Any:
    """thread-safe boto3 S3 client 생성"""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def validate_files(files: list[dict[str, str]]) -> None:
    """파일명, MIME, 크기 등 사전 검증 로직 (추후 구현 예정)"""
    # TODO: 파일명, 확장자, content-type, 크기 검증 추가
    pass


def generate_presigned_urls(prefix: str, files: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Presigned URL 생성"""
    s3 = get_s3_client()
    presigned_data: list[dict[str, Any]] = []

    for file in files:
        file_name = file.get("file_name")
        content_type = file.get("content_type")

        key = f"{prefix}{uuid.uuid4()}_{file_name}"

        presigned_post = s3.generate_presigned_post(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 0, 10 * 1024 * 1024],  # 10MB 이하
            ],
            ExpiresIn=300,  # 5분
        )

        presigned_data.append(
            {
                "file_name": file_name,
                "key": key,
                "url": presigned_post["url"],
                "fields": presigned_post["fields"],
            }
        )

    return presigned_data
