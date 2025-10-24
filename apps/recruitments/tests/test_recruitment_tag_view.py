from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.recruitments.models import Recruitment, RecruitmentTag, Tag


@pytest.mark.django_db
class TestRecruitmentTagView:
    """RecruitmentTag 관련 API 테스트"""

    client: APIClient
    recruitment: Recruitment
    tag: Tag

    def setup_method(self) -> None:
        """테스트용 기본 데이터 세팅"""
        self.client = APIClient()
        self.recruitment = Recruitment.objects.create(title="백엔드 모집", content="Django 개발자 구인")
        self.tag = Tag.objects.create(name="Python")

    def test_get_recruitment_tags_empty(self) -> None:
        """태그가 없을 때 404 반환"""
        response: Response = self.client.get(f"/api/recruitments/{self.recruitment.id}/tags/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "이 구인 공고에 연결된 태그가 없습니다" in str(response.data)

    def test_post_recruitment_tag(self) -> None:
        """태그를 새로 추가"""
        data: dict[str, int] = {"tag": self.tag.id}
        response: Response = self.client.post(f"/api/recruitments/{self.recruitment.id}/tags/", data)
        assert response.status_code == status.HTTP_201_CREATED
        assert RecruitmentTag.objects.filter(recruitment=self.recruitment, tag=self.tag).exists()

    def test_post_recruitment_tag_invalid(self) -> None:
        """유효하지 않은 데이터로 태그 추가 시 400 반환"""
        data: dict[str, None] = {"tag": None}
        response: Response = self.client.post(f"/api/recruitments/{self.recruitment.id}/tags/", data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_recruitment_tag(self) -> None:
        """태그 연결 삭제"""
        rt: RecruitmentTag = RecruitmentTag.objects.create(recruitment=self.recruitment, tag=self.tag)
        response: Response = self.client.delete(f"/api/recruitments/{self.recruitment.id}/tags/{self.tag.id}/")
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_200_OK,
        ]

        assert not RecruitmentTag.objects.filter(recruitment=self.recruitment, tag=self.tag).exists()

    def test_delete_nonexistent_tag(self) -> None:
        """존재하지 않는 태그 삭제 시 404 반환"""
        response: Response = self.client.delete(f"/api/recruitments/{self.recruitment.id}/tags/9999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
