from __future__ import annotations

import logging
import uuid
from typing import Any, ClassVar, Optional, cast

import boto3  # type: ignore
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from rest_framework.exceptions import APIException, ParseError, ValidationError

from apps.core.constants.s3_allowed_extensions import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ATTACHMENT_MIME_BY_EXT,
    IMAGE_MIME_BY_EXT,
)

logger = logging.getLogger(__name__)

###################################
# 공통 S3 Presigned URL 유틸리티 모듈
# - boto3 클라이언트 생성 후 재사용
# - Presigned URL 생성 (POST)
# - 파일 검증
# - 단건/복수 삭제
###################################


class S3Uploader:
    """
    공통 S3 업로더 클래스 (boto3 기반)
    - boto3 클라이언트 생성
    - Presigned URL 생성
    - 단일 / 복수 객체 삭제
    - 파일 업로드 (테스트 및 관리용)
    """

    s3_client: Any = boto3.client(
        "s3",
        aws_access_key_id=getattr(settings, "AWS_S3_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_S3_SECRET_ACCESS_KEY", None),
        region_name=getattr(settings, "AWS_S3_REGION", None),
    )
    BUCKET_NAME: ClassVar[str] = getattr(settings, "AWS_S3_BUCKET_NAME", "")
    REGION_NAME: ClassVar[str] = getattr(settings, "AWS_S3_REGION", "")
    S3_BASE_URL: ClassVar[str] = f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/"

    @classmethod
    def validate_file_name(cls, file: UploadedFile) -> None:
        """File 이름 검증"""
        if file.name is None or file.name == "":
            raise ValidationError("유효하지 않은 파일명입니다.")
        if "." not in file.name or file.name.rsplit(".", 1)[0] == "":
            raise ValidationError("유효하지 않은 파일명입니다.")

    @classmethod
    def validate_file_extension(cls, file: UploadedFile) -> None:
        """
        파일 확장자 검증
        constants/s3_allowed_extensions 상수 사용
        """
        ext = cast(str, file.name).rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_IMAGE_EXTENSIONS or ext in ALLOWED_ATTACHMENT_EXTENSIONS:
            return

        raise ValidationError("허용된 확장자만 등록 가능합니다.")

    @classmethod
    def validate_file_content_type(cls, content_type: Optional[str]) -> None:
        """
        파일 확장자 검증
        constants/s3_allowed_extensions 상수 사용
        """
        # 내장함수 any로 이 블록 안에서는 content_type은 str이게끔
        if content_type and any(content_type in m for m in IMAGE_MIME_BY_EXT.values()):
            return

        raise ValidationError("허용된 확장자(MIME)만 등록 가능합니다.")

    @classmethod
    def validate_file_mime(cls, ext: str, content_type: Optional[str]) -> None:
        """
        MIME 타입 검증
        constants/s3_allowed_extensions 상수 사용
        """
        if not content_type:
            raise ParseError("유효한 Content-Type이 필요합니다.")
        # 매핑 통합 조회
        if ext in IMAGE_MIME_BY_EXT:
            if content_type not in IMAGE_MIME_BY_EXT[ext]:
                raise ValidationError("허용된 이미지 확장자/형식만 등록 가능합니다.")
            return

        if ext in ATTACHMENT_MIME_BY_EXT:
            if content_type not in ATTACHMENT_MIME_BY_EXT[ext]:
                raise ValidationError("허용된 첨부파일 확장자/형식만 등록 가능합니다.")
            return

        # 확장자 검증을 통과했다면 일반적으로 도달하지 않음(이중 방어)
        raise ValidationError("허용된 확장자만 등록 가능합니다.")

    @classmethod
    def upload_file(cls, file: UploadedFile, prefix: str) -> str:
        """파일 업로드"""

        ext = cast(str, file.name).rsplit(".", 1)[-1].lower()

        # prefix 보정
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        key = f"{prefix}{uuid.uuid4().hex}.{ext}"

        try:
            cls.s3_client.upload_fileobj(
                Fileobj=file,
                Bucket=cls.BUCKET_NAME,
                Key=key,
            )
            return cls.S3_BASE_URL + key
        except Exception as e:
            logger.error("로깅 메시지", exc_info=True)
            raise APIException(f"Unexpected S3 Upload Error: {str(e)}")

    @classmethod
    def generate_presigned_urls(cls, prefix: str, files: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Presigned URL 생성"""
        presigned_data: list[dict[str, Any]] = []

        # prefix 보정
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        for file in files:
            file_name = file.get("file_name")
            content_type = file.get("content_type")

            ext = cast(str, file_name).rsplit(".", 1)[-1].lower()

            key = f"{prefix}{uuid.uuid4()}_{file_name}.{ext}"

            try:
                presigned_post = cls.s3_client.generate_presigned_post(
                    Bucket=cls.BUCKET_NAME,
                    Key=key,
                    Fields={"acl": "public-read", "Content-Type": content_type},
                    Conditions=[
                        {"acl": "public-read"},
                        {"Content-Type": content_type},
                        ["content-length-range", 1, 10 * 1024 * 1024],
                    ],
                    ExpiresIn=300,
                )
            except Exception as e:
                logger.error("S3 Generate Presigned POST Error", exc_info=True)
                raise APIException(f"Unexpected S3 Presign Error: {str(e)}")

            presigned_data.append(
                {
                    "file_name": file_name,
                    "key": key,
                    "url": presigned_post["url"],
                    "fields": presigned_post["fields"],
                    "file_url": cls.S3_BASE_URL + key,
                    "expires_in": 300,
                }
            )

        return presigned_data

    @classmethod
    def delete_file(cls, key: str) -> None:
        """단일 파일삭제 (S3.Client.delete_object)"""
        try:
            cls.s3_client.delete_object(Bucket=cls.BUCKET_NAME, Key=key)
        except Exception as e:
            logger.error("로깅 메세지")
            raise APIException(f"Unexpected S3 Delete Object Error: {str(e)}")

    @classmethod
    def delete_files(cls, keys: list[str]) -> None:
        """복수 파일 삭제 (S3.Client.delete_objects)"""
        key_map = {"Objects": [{"Key": key} for key in keys]}
        try:
            cls.s3_client.delete_objects(Delete=key_map, Bucket=cls.BUCKET_NAME)
        except Exception as e:
            logger.error("로깅 메시지")
            raise APIException(f"Unexpected S3 Delete Objects Error: {str(e)}")
