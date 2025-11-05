from __future__ import annotations

from typing import TypedDict

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

    요청 예시:
    {
      "files": [
        {"file_name": "cover.png", "content_type": "image/png"}
      ]
    }

    응답 예시:
    {
      "status": 200,
      "message": "Presigned URL 발급이 완료되었습니다.",
      "data": [
        {
          "file_name": "cover.png",
          "key": "uploads/studies/groups/<uuid>_cover.png",
          "url": "<S3 presigned upload URL>",
          "fields": { ... },
          "file_url": "<완성된 최종 접근 가능한 URL>",
          "expires_in": 300
        }
      ]
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = PresignedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = serializer.validated_data["files"]
        presigned_data = []

        for f in files:
            content_type = f["content_type"]
            if not content_type.startswith("image/"):
                return Response(
                    {
                        "status": 400,
                        "message": "잘못된 요청입니다.",
                        "error": {
                            "code": "INVALID_FILE_TYPE",
                            "detail": f"{content_type} 형식은 지원되지 않습니다.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            prefix = GROUP_IMAGE_PREFIX
            presigned = S3Uploader.generate_presigned_urls(prefix, [f])[0]
            presigned_data.append(presigned)

        return Response(
            {
                "status": 200,
                "message": "Presigned URL 발급이 완료되었습니다.",
                "data": presigned_data,
            },
            status=status.HTTP_200_OK,
        )


class StudyNoteS3PresignedView(APIView):
    """
    스터디 노트 첨부파일 및 이미지 업로드용 Presigned URL 발급 API
    - 노트 작성/수정 시 파일 또는 이미지 업로드를 위한 URL 반환

    요청 예시:
    {
      "files": [
        {"file_name": "diagram.png", "content_type": "image/png"},
        {"file_name": "summary.pdf", "content_type": "application/pdf"}
      ]
    }

    응답 예시:
    {
      "status": 200,
      "message": "Presigned URL 발급이 완료되었습니다.",
      "data": [
        {
          "file_name": "diagram.png",
          "key": "uploads/studies/notes/<uuid>_diagram.png",
          "url": "<S3 presigned upload URL>",
          "fields": { ... },
          "file_url": "<완성된 최종 접근 가능한 URL>",
          "expires_in": 300
        },
        ...
      ]
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = PresignedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = serializer.validated_data["files"]
        presigned_data = []

        for f in files:
            content_type = f["content_type"]
            prefix = NOTE_IMAGE_PREFIX if content_type.startswith("image/") else NOTE_FILE_PREFIX
            presigned = S3Uploader.generate_presigned_urls(prefix, [f])[0]
            presigned_data.append(presigned)

        return Response(
            {
                "status": 200,
                "message": "Presigned URL 발급이 완료되었습니다.",
                "data": presigned_data,
            },
            status=status.HTTP_200_OK,
        )
