from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recruitments.models import Recruitment, Tag
from apps.users.models import User


class AdminRecruitmentAPITestCase(TestCase):
    """관리자용 스터디 구인공고 API 통합 테스트"""

    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        # 관리자 생성
        self.admin_user = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            birthday=date(1990, 1, 1),
            nickname="관리자",
            phone_number="01012345678",
        )
        self.client.force_authenticate(user=self.admin_user)

        # 테스트용 태그 및 공고 생성
        self.tag_python = Tag.objects.create(name="Python")
        self.tag_django = Tag.objects.create(name="Django")

        self.recruitment = Recruitment.objects.create(
            author=self.admin_user,
            title="테스트 공고",
            content="테스트용 공고 내용입니다.",
            estimated_fee=10000,
            expected_headcount=3,
            views_count=15,
        )
        self.recruitment.tags.add(self.tag_python)

    # 목록 조회
    def test_admin_can_list_recruitments(self) -> None:
        """관리자 전체 공고 목록 조회"""
        url = reverse("admin-recruitment-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()

        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertEqual(data["results"][0]["title"], "테스트 공고")

    def test_admin_can_filter_by_tags(self) -> None:
        """태그 필터링 기능"""
        url = f"{reverse('admin-recruitment-list')}?tags=Python&tags=Django"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("results", data)

    def test_admin_can_filter_open_and_closed(self) -> None:
        """is_closed 필터 테스트"""
        # 마감 상태로 변경
        self.recruitment.is_closed = True
        self.recruitment.save()

        url_closed = f"{reverse('admin-recruitment-list')}?is_closed=true"
        res_closed = self.client.get(url_closed)
        self.assertEqual(res_closed.status_code, status.HTTP_200_OK)
        for item in res_closed.json()["results"]:
            self.assertTrue(item["is_closed"])

        url_open = f"{reverse('admin-recruitment-list')}?is_closed=false"
        res_open = self.client.get(url_open)
        self.assertEqual(res_open.status_code, status.HTTP_200_OK)
        for item in res_open.json()["results"]:
            self.assertFalse(item["is_closed"])

    # 상세 조회
    def test_admin_can_retrieve_recruitment_detail(self) -> None:
        """관리자 상세 조회"""
        url = reverse("admin-recruitment-detail", args=[self.recruitment.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertEqual(body["title"], "테스트 공고")
        self.assertIn("tags", body)
        self.assertIn("attachments", body)
        self.assertIn("applications", body)

    def test_retrieve_nonexistent_recruitment_returns_404(self) -> None:
        """존재하지 않는 공고 조회 시 404"""
        url = reverse("admin-recruitment-detail", args=[9999])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", res.json())

    # 삭제
    def test_admin_can_delete_recruitment(self) -> None:
        """관리자 공고 삭제"""
        url = reverse("admin-recruitment-detail", args=[self.recruitment.id])
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Recruitment.objects.filter(id=self.recruitment.id).exists(),
            "삭제 이후에도 공고가 존재함",
        )

    def test_delete_nonexistent_recruitment_returns_404(self) -> None:
        """존재하지 않는 공고 삭제 시 404"""
        url = reverse("admin-recruitment-detail", args=[9999])
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", res.json())

    # 권한
    def test_non_admin_cannot_access_admin_endpoints(self) -> None:
        """비관리자 접근 시 403"""
        user = User.objects.create_user(
            email="user@test.com",
            password="user1234",
            birthday=date(1995, 5, 5),
            nickname="일반유저",
            phone_number="01099998888",
        )
        self.client.force_authenticate(user=user)
        url = reverse("admin-recruitment-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
