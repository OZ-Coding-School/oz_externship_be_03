from __future__ import annotations

from typing import Any, Dict, List

from rest_framework import serializers


class PresignedFileSerializer(serializers.Serializer[Any]):
    file_name = serializers.CharField()
    content_type = serializers.CharField()


class PresignedRequestSerializer(serializers.Serializer[Any]):
    """
    Presigned URL 발급 요청 검증용 Serializer
    {
      "files": [
        {"file_name": "example.png", "content_type": "image/png"},
        {"file_name": "notes.pdf", "content_type": "application/pdf"}
      ]
    }
    """

    files = PresignedFileSerializer(many=True)

    def validate_files(self, value: List[dict[str, str]]) -> List[Dict[str, str]]:
        if len(value) == 0:
            raise serializers.ValidationError("최소 1개 이상의 파일을 업로드해주세요")

        for f in value:  # 업로드 전 단계 외부입력 검증용도
            if "file_name" not in f or "content_type" not in f:
                raise serializers.ValidationError("file_name, content_type는 필수입니다.")
            if not isinstance(f["file_name"], str) or not isinstance(f["content_type"], str):
                raise serializers.ValidationError("file_name, content_type는 문자열이어야 합니다.")

        return value
