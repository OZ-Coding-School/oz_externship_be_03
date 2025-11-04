import typing
from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recruitments.models.search_log import SearchLog
from apps.users.models import User


class SearchLogAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="loguser@example.com",
            password="testpass",
            birthday=date(1999, 5, 5),
            name="로그유저",
            nickname="logger",
            phone_number="010-5678-1234",
            gender="FEMALE",
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_create_search_log(self) -> None:
        url = reverse("searchlog-list-create")
        payload = {"q": "Django", "filters": {"status": "OPEN"}}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        log = SearchLog.objects.first()
        self.assertIsNotNone(log)
        log = typing.cast(SearchLog, log)
        self.assertEqual(log.q, "Django")
        self.assertEqual(log.filters["status"], "OPEN")
        self.assertEqual(log.user, self.user)
