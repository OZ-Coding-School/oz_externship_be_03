from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class StudyGroupTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_group_list_success(self) -> None:
        """스터디 그룹 목록 조회 성공 테스트"""
        response = self.client.get("/api/v1/studies/groups/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_group_detail_not_found(self) -> None:
        """존재하지 않는 그룹 상세 조회 시 404"""
        response = self.client.get("/api/v1/studies/groups/999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_group_create_invalid(self) -> None:
        """잘못된 데이터로 생성 요청 시 400"""
        invalid_data = {"name": ""}
        response = self.client.post("/api/v1/studies/groups/", invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
