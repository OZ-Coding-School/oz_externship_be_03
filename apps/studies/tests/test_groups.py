from django.test import Client, TestCase
from rest_framework import status


class StudyGroupListCreateViewTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.url = "/api/v1/studies/groups/"

    def test_post_create_study_group(self) -> None:
        """
        POST 요청 테스트
        - 상태 코드 201
        """
        payload = {
            "name": "Test Group",
            "introduction": "This is Test Group",
            "profile_img_url": "https://example.com/test1.jpg",
            "max_headcount": 5,
            "start_at": "2025-11-01",
            "end_at": "2025-11-10",
            "status": "PENDING",
            "lectures": [1, 2],
        }
        response = self.client.post(self.url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_study_group_list(self) -> None:
        """
        GET 요청 테스트
        - 상태 코드 200
        - 그룹 리스트 구조 확인
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(len(data), 10)

        first_group = data[0]
        self.assertIn("id", first_group)
        self.assertIn("name", first_group)
        self.assertIn("current_headcount", first_group)
        self.assertIn("max_headcount", first_group)
        self.assertIn("is_leader", first_group)
        self.assertIn("profile_img_url", first_group)
        self.assertIn("start_at", first_group)
        self.assertIn("end_at", first_group)
        self.assertIn("status", first_group)
        self.assertIn("lectures", first_group)
