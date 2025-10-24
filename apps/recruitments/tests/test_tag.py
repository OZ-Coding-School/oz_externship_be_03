from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.recruitments.models import Tag


@pytest.mark.django_db
class TestTagView:
    """Tag 관련 API 테스트"""

    client: APIClient

    def setup_method(self) -> None:
        """테스트 초기 설정"""
        self.client = APIClient()

    def test_get_tags(self) -> None:
        """전체 태그 목록 조회"""
        Tag.objects.create(name="Django")
        Tag.objects.create(name="Python")

        response: Response = self.client.get("/api/recruitments/tags/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) >= 2

    def test_post_tag(self) -> None:
        """새로운 태그 생성"""
        data: dict[str, str] = {"name": "FastAPI"}
        response: Response = self.client.post("/api/recruitments/tags/", data)
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]
        assert Tag.objects.filter(name="FastAPI").exists()

    def test_post_tag_duplicate(self) -> None:
        """중복 태그 생성 시 예외 발생"""
        Tag.objects.create(name="React")
        data: dict[str, str] = {"name": "React"}
        response: Response = self.client.post("/api/recruitments/tags/", data)
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]
