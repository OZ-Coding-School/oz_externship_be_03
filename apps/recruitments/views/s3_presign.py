from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.constants.storage_prefix import (
    RECRUIT_FILE_PREFIX,
    RECRUIT_IMAGE_PREFIX,
)
from apps.core.utils.s3_uploader import S3Uploader
from apps.studies.serializers.s3_presign import PresignedRequestSerializer


class RecruitmentS3PresignedView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Recruitments"],
        request=PresignedRequestSerializer(many=True),
        responses={
            200: inline_serializer(
                name="PresignedRequestResponse",
                fields={
                    "status": serializers.IntegerField(),
                    "message": serializers.CharField(),
                    "data": serializers.ListField(
                        child=inline_serializer(
                            name="PresignedDataSerializer",
                            fields={
                                "file_name": serializers.CharField(),
                                "key": serializers.CharField(),
                                "url": serializers.URLField(),
                                "fields": serializers.DictField(),
                                "file_url": serializers.URLField(),
                                "expires_in": serializers.IntegerField(),
                            },
                        )
                    ),
                },
            ),
        },
    )
    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = PresignedRequestSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        file_data = serializer.validated_data

        presigned_urls: list[dict[str, Any]] = []

        for f in file_data:
            file_name = f["file_name"]
            content_type = f["content_type"]

            S3Uploader.validate_file_obj_name(file_name)

            ext = file_name.rsplit(".", 1)[-1].lower()
            S3Uploader.validate_file_content_type(content_type)
            S3Uploader.validate_file_mime(ext, content_type)
            S3Uploader.validate_file_str_extension(file_name)

            prefix = RECRUIT_IMAGE_PREFIX if content_type.startswith("image/") else RECRUIT_FILE_PREFIX

            presigned_urls = S3Uploader.generate_presigned_urls(prefix, file_data)

        return Response(
            {
                "status": 200,
                "message": "Presigned URL 발급이 완료되었습니다.",
                "data": presigned_urls,
            },
            status=status.HTTP_200_OK,
        )
