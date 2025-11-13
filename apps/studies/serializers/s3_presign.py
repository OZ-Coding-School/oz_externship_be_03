from __future__ import annotations

from typing import Any, Dict, List

from rest_framework import serializers


class PresignedFileSerializer(serializers.Serializer[Any]):
    file_name = serializers.CharField()
    content_type = serializers.CharField()
    file_size = serializers.IntegerField()


class PresignedRequestSerializer(serializers.Serializer[Any]):
    """
    Presigned URL 발급 요청 검증용 Serializer
    """

    files = PresignedFileSerializer(many=True)

    def validate_files(self, value: List[dict[str, Any]]) -> List[Dict[str, Any]]:
        if not value:
            raise serializers.ValidationError("최소 1개 이상의 파일을 업로드해주세요.")

        for f in value:
            # 필드 존재 여부
            required_fields = ("file_name", "content_type", "file_size")
            for field in required_fields:
                if field not in f:
                    raise serializers.ValidationError(f"{field}는 필수입니다.")
            # file_name 검증
            if not isinstance(f["file_name"], str) or not f["file_name"].strip():
                raise serializers.ValidationError("file_name은 비어 있지 않은 문자열이어야 합니다.")
            # content_type 검증
            if not isinstance(f["content_type"], str) or not f["content_type"].strip():
                raise serializers.ValidationError("content_type은 비어 있지 않은 문자열이어야 합니다.")
            # file_size 검증
            if not isinstance(f["file_size"], int) or f["file_size"] <= 0:
                raise serializers.ValidationError("file_size는 0보다 큰 정수여야 합니다.")
        return value
