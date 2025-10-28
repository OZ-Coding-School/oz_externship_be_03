from __future__ import annotations

import random
from datetime import date
from typing import ClassVar, Final
from uuid import uuid4

from django.test import Client, TestCase
from django.urls import reverse

from apps.users.models.user import User

DEFAULT_PWD: Final[str] = "Passw0rd!"


def make_user(
    *,
    email: str | None = None,
    password: str = DEFAULT_PWD,
    name: str = "홍길동",
    nickname: str | None = None,
    phone_number: str | None = None,
    gender: str = "M",
    birthday: date = date(1990, 1, 1),
    is_active: bool = True,
) -> User:
    """유저 생성"""
    suffix = uuid4().hex[:6]
    if email is None:
        email = f"user{suffix}@example.com"
    if nickname is None:
        nickname = f"nick{suffix}"
    if phone_number is None:
        phone_number = f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

    user = User.objects.create_user(
        email=email,
        password=password,
        name=name,
        nickname=nickname,
        phone_number=phone_number,
        gender=gender,
        birthday=birthday,
    )
    if user.is_active != is_active:
        user.is_active = is_active
        user.save(update_fields=["is_active"])
    return user


class UserDupNicknameViewTests(TestCase):
    existing: ClassVar[User]
    url: ClassVar[str]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.existing = make_user(nickname="Winter")
        cls.url = reverse("users:dup_nickname")

    def setUp(self) -> None:
        self.client = Client()

    def test_missing_nickname_returns_400(self) -> None:
        # nickname 미제공
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

        # 공백만 전달
        resp2 = self.client.get(self.url, {"nickname": "   "})
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("error", resp2.json())

    def test_default_case_insensitive_duplicates(self) -> None:
        # 기본값: 대소문자 구분 안함 → Winter vs winter => 중복
        resp = self.client.get(self.url, {"nickname": "winter"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("detail", body)
        self.assertIn("data", body)
        self.assertEqual(body["data"]["nickname"], "winter")
        self.assertFalse(body["data"]["available"])  # 중복

    def test_not_duplicate_when_not_exists(self) -> None:
        resp = self.client.get(self.url, {"nickname": "BrandNewNick"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["data"]["available"])  # 사용 가능
        self.assertEqual(body["data"]["nickname"], "BrandNewNick")

    def test_case_sensitive_false_flag(self) -> None:
        # case_insensitive=false → 대소문자 지켜서 중복 확인
        resp = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "false"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["data"]["available"])

        resp2 = self.client.get(self.url, {"nickname": "Winter", "case_insensitive": "false"})
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.json()["data"]["available"])

    def test_trims_spaces(self) -> None:
        # 앞뒤 공백 제거되어 Winter 비교 → 중복
        resp = self.client.get(self.url, {"nickname": "  Winter  "})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["data"]["available"])

    def test_truthy_values_for_case_insensitive(self) -> None:
        # true/1만 true로 처리 ({"1","true"}만 true)
        # "true" → 중복
        resp_true = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "true"})
        self.assertFalse(resp_true.json()["data"]["available"])

        # "1" → 중복
        resp_one = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "1"})
        self.assertFalse(resp_one.json()["data"]["available"])

        # "0" → false 처리 → 대소문 구분
        resp_yes = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "0"})
        self.assertTrue(resp_yes.json()["data"]["available"])
