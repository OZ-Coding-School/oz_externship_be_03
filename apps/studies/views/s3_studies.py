# apps/studies/views/s3_studies.py
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils.s3_uploader import generate_presigned_urls, validate_files


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
        files = request.data.get("files", [])
        validate_files(files)

        presigned_data = generate_presigned_urls("uploads/studies/groups/", files)
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
        files = request.data.get("files", [])
        validate_files(files)

        presigned_data = generate_presigned_urls("uploads/studies/notes/", files)
        return Response(
            {
                "status": 200,
                "message": "Presigned URL 발급이 완료되었습니다.",
                "data": presigned_data,
            },
            status=status.HTTP_200_OK,
        )
