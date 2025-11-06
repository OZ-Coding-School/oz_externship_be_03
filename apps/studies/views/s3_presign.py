from __future__ import annotations

from typing import TypedDict

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.constants.storage_prefix import (
    GROUP_IMAGE_PREFIX,
    NOTE_FILE_PREFIX,
    NOTE_IMAGE_PREFIX,
)
from apps.core.utils.s3_uploader import S3Uploader
from apps.studies.serializers.s3_presign import PresignedRequestSerializer


class StudyGroupS3PresignedView(APIView):
    """
    스터디 그룹 대표 이미지 업로드용 Presigned URL 발급 API
    - 그룹 생성/수정 시 대표 이미지 업로드를 위한 URL 반환
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PresignedRequestSerializer,
        responses={
            200: PresignedRequestSerializer,
        }
    )
    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = PresignedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = serializer.validated_data["files"]

        for f in files:
            S3Uploader.validate_file_content_type(f.get("content_type"))

        prefix = GROUP_IMAGE_PREFIX
        #대표 이미지는 단일 업로드겠지만 노트와 공용시리얼라이저 사용 + 썸네일 도입 등을 감안해서 files 복수형 유지
        presigned_urls = S3Uploader.generate_presigned_urls(prefix, files)[0] # 이중리스트같아서 리스트 감싸기 해제

        return Response(
            {
                "status": 200,
                "message": "Presigned URL 발급이 완료되었습니다.",
                "data": presigned_urls,
            },
            status=status.HTTP_200_OK,
        )


class StudyNoteS3PresignedView(APIView):
    """
    스터디 노트 첨부파일 및 이미지 업로드용 Presigned URL 발급 API
    - 노트 작성/수정 시 파일 또는 이미지 업로드를 위한 URL 반환
    """

    permission_classes = [IsAuthenticated]
    @extend_schema(
        request=PresignedRequestSerializer,
        responses={
            200: PresignedRequestSerializer,
        }
    )

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = PresignedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = serializer.validated_data["files"]

        for f in files:
            S3Uploader.validate_file_content_type(f.get("content_type"))
            content_type = f.get("content_type")

            prefix = NOTE_IMAGE_PREFIX if content_type.startswith("image/") else NOTE_FILE_PREFIX

            presigned_urls = S3Uploader.generate_presigned_urls(prefix, files) # 멀티 업로드 경우 대비 [0] 제거

        return Response(
            {
                "status": 200,
                "message": "Presigned URL 발급이 완료되었습니다.",
                "data": presigned_urls,
            },
            status=status.HTTP_200_OK,
        )