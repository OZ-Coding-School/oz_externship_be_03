from django.urls import reverse
from rest_framework.test import APITestCase

from apps.recruitments.models import Tag
from apps.users.models import User


class TagApiTestCase(APITestCase):
    user: User
    url: str

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create(
            email="user1@example.com",
            password="password123",
            nickname="user1",
            phone_number="01011112222",
            name="User One",
            gender="M",
            birthday="2000-01-01",
        )
        cls.url = reverse("recruitments:tags")

    def setUp(self) -> None:
        self.client = self.client_class()

    def _create_tags(self) -> list[Tag]:
        tags = [Tag(name=f"tag{i}") for i in range(1, 10)]
        return Tag.objects.bulk_create(tags)

    def test_tag_create_api_success(self) -> None:
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"name": (tag_name := "tag1")})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], tag_name)
        self.assertTrue(Tag.objects.filter(name=tag_name).exists())

    def test_tag_create_api_fail_without_authenticate(self) -> None:
        response = self.client.post(self.url, {"name": "tag"})
        self.assertEqual(response.status_code, 401)

    def test_tag_create_api_fail_with_blank_tag_name(self) -> None:
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {"name": ""})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["name"][0]), "이 필드는 blank일 수 없습니다.")

    def test_tag_list_api_success(self) -> None:
        # given
        self._create_tags()

        # when
        response = self.client.get(self.url)

        # then
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(len(response.data["results"]), 9)
        self.assertEqual(response.data["count"], 9)

    def test_tag_list_api_fail_with_pagination(self) -> None:
        # given
        self._create_tags()

        # when
        response = self.client.get(self.url, query_params={"page": 1, "page_size": 3})

        # then
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertEqual(response.data["count"], 9)

    def test_tag_list_api_fail_with_search_query_param(self) -> None:
        # given
        tags = self._create_tags()

        # when
        response = self.client.get(self.url, query_params={"search": tags[0].name})

        # then
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], tags[0].name)
