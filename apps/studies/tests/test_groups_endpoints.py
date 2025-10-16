# mypy: ignore-errors
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class StudyGroupEndpointsTests(APITestCase):
    def test_group_list_view(self):
        url = reverse("group-list")
        res = self.client.get(url)
        assert res.status_code == status.HTTP_200_OK

    def test_group_detail_view(self):
        url = reverse("group-detail", args=[1])
        res = self.client.get(url)
        assert res.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_group_create_view(self):
        url = reverse("group-create")
        payload = {
            "name": "테스트 스터디",
            "introduction": "테스트용 생성입니다.",
            "max_members": 5,
            "start_at": "2025-11-01",
            "end_at": "2025-11-10",
        }
        res = self.client.post(url, payload, format="json")
        assert res.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

    def test_group_update_view(self):
        url = reverse("group-update", args=[1])
        payload = {"name": "수정된 스터디"}
        res = self.client.put(url, payload, format="json")
        assert res.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_group_delete_view(self):
        url = reverse("group-detail", args=[1])
        res = self.client.delete(url)
        assert res.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_group_lectures_view(self):
        # lectures URL은 group_id를 받지 않음
        url = reverse("group-lectures", args=[1])
        res = self.client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert "lectures" in res.data or "results" in res.data

    def test_group_status_auto_update_view(self):
        url = reverse("group-status-auto")
        res = self.client.get(url)
        assert res.status_code == status.HTTP_200_OK
