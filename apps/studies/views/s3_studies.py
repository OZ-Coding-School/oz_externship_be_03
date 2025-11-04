from __future__ import annotations

from typing import Any, Dict, List, TypedDict, cast

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.utils.s3_uploader import S3Uploader


class PresignFile(TypedDict):
    file_name: str
    content_type: str


class StudyGroupS3PresignedView(APIView):
    """
    스터디 그룹 대표 이미지 업로드용 Presigned URL 발급 API
    - 그룹 생성/수정 시 대표 이미지 업로드를 위한 URL 반환
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        """
        요청 예시:
        {
          "files": [
            {"file_name": "cover.png", "content_type": "image/png"}
          ]
        }
        """
        raw_files: Any = request.data.get("files", [])

        # 최소 인라인 검증 + 타입 좁히기
        if not isinstance(raw_files, list):
            return Response(
                {
                    "status": 400,
                    "message": "잘못된 요청입니다.",
                    "error": {"code": "INVALID_FILES_PAYLOAD", "detail": "files는 리스트여야 합니다."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        for i, it in enumerate(raw_files):
            if not isinstance(it, dict):
                return Response(
                    {
                        "status": 400,
                        "message": "잘못된 요청입니다.",
                        "error": {"code": "INVALID_FILES_ITEM", "detail": f"files[{i}]는 객체여야 합니다."},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not isinstance(it.get("file_name"), str) or not isinstance(it.get("content_type"), str):
                return Response(
                    {
                        "status": 400,
                        "message": "잘못된 요청입니다.",
                        "error": {
                            "code": "INVALID_FILES_FIELDS",
                            "detail": f"files[{i}]의 file_name, content_type는 문자열이어야 합니다.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        files_typed = cast(List[PresignFile], raw_files)  # mypy: List[PresignFile]로 확정
        files = cast(List[Dict[str, str]], files_typed)  # S3Uploader 시그니처(list[dict[str,str]])와 호환

        presigned_data = S3Uploader.generate_presigned_urls("uploads/studies/groups/", files)

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
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        """
        요청 예시:
        {
          "files": [
            {"file_name": "diagram.png", "content_type": "image/png"},
            {"file_name": "notes.pdf", "content_type": "application/pdf"}
          ]
        }
        """
        raw_files: Any = request.data.get("files", [])

        # 최소 인라인 검증 + 타입 좁히기
        if not isinstance(raw_files, list):
            return Response(
                {
                    "status": 400,
                    "message": "잘못된 요청입니다.",
                    "error": {"code": "INVALID_FILES_PAYLOAD", "detail": "files는 리스트여야 합니다."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        for i, it in enumerate(raw_files):
            if not isinstance(it, dict):
                return Response(
                    {
                        "status": 400,
                        "message": "잘못된 요청입니다.",
                        "error": {"code": "INVALID_FILES_ITEM", "detail": f"files[{i}]는 객체여야 합니다."},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not isinstance(it.get("file_name"), str) or not isinstance(it.get("content_type"), str):
                return Response(
                    {
                        "status": 400,
                        "message": "잘못된 요청입니다.",
                        "error": {
                            "code": "INVALID_FILES_FIELDS",
                            "detail": f"files[{i}]의 file_name, content_type는 문자열이어야 합니다.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        files_typed = cast(List[PresignFile], raw_files)  # mypy: List[PresignFile]로 확정
        files = cast(List[Dict[str, str]], files_typed)  # S3Uploader 시그니처와 호환

        presigned_data = S3Uploader.generate_presigned_urls("uploads/studies/notes/", files)

        return Response(
            {
                "status": 200,
                "message": "Presigned URL 발급이 완료되었습니다.",
                "data": presigned_data,
            },
            status=status.HTTP_200_OK,
        )
