from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recruitments.models import Recruitment
from apps.users.models import User


class AdminRecruitmentAPITestCase(TestCase):
    # 관리자용 스터디 구인공고 API 테스트
    def setUp(self) -> None:
        # APIClient 타입 명시
        self.client: APIClient = APIClient()

        # 관리자 계정 및 기본 공고 생성
        self.admin_user = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            birthday=date(1990, 1, 1),
            nickname="관리자",
            phone_number="01012345678",
        )
        self.client.force_authenticate(user=self.admin_user)

        self.recruitment = Recruitment.objects.create(
            author=self.admin_user,
            title="테스트 공고",
            content="테스트용 공고 내용입니다.",
            estimated_fee=10000,
            expected_headcount=3,
            views_count=15,
        )

    # 목록 조회
    def test_admin_can_list_recruitments(self) -> None:
        # 관리자가 전체 공고 목록을 조회할 수 있는지 확인
        url = reverse("admin_recruitment_list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, "목록 조회 응답 코드가 올바르지 않음")
        data = res.json()
        results = data["results"] if "results" in data else data
        self.assertEqual(results[0]["title"], "테스트 공고")

    def test_admin_can_filter_closed_recruitments(self) -> None:
        # 마감된 공고만 반환되는지 확인
        self.recruitment.is_closed = True
        self.recruitment.save()
        url = f"{reverse('admin_recruitment_list')}?is_closed=true"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        results = data["results"] if "results" in data else data
        for item in results:
            self.assertTrue(item["is_closed"], "마감된 공고만 반환되지 않음")

    def test_admin_can_filter_open_recruitments(self) -> None:
        # 진행 중인 공고만 반환되는지 확인
        url = f"{reverse('admin_recruitment_list')}?is_closed=false"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        results = data["results"] if "results" in data else data
        for item in results:
            self.assertFalse(item["is_closed"], "진행 중 공고만 반환되지 않음")

    def test_admin_can_filter_by_tag_name(self) -> None:
        # 태그명으로 필터링 시 정상 응답 확인
        url = f"{reverse('admin_recruitment_list')}?tag=테스트"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # 상세 조회
    def test_admin_can_retrieve_recruitment_detail(self) -> None:
        # 관리자가 특정 공고 상세 정보를 조회할 수 있는지 확인
        url = reverse("admin_recruitment_detail", args=[self.recruitment.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["title"], "테스트 공고")

    def test_retrieve_nonexistent_recruitment_returns_404(self) -> None:
        # 존재하지 않는 공고 조회 시 404 응답 반환 확인
        url = reverse("admin_recruitment_detail", args=[9999])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("message", res.json())

    # 삭제
    def test_admin_can_delete_recruitment(self) -> None:
        # 관리자가 공고를 정상적으로 삭제할 수 있는지 확인
        url = reverse("admin_recruitment_detail", args=[self.recruitment.id])
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Recruitment.objects.filter(id=self.recruitment.id).exists(),
            "삭제 이후에도 공고가 존재함",
        )

    def test_delete_nonexistent_recruitment_returns_404(self) -> None:
        # 존재하지 않는 공고 삭제 시 404 응답 반환 확인
        url = reverse("admin_recruitment_detail", args=[9999])
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("message", res.json())

    # 권한
    def test_non_admin_cannot_access_admin_endpoints(self) -> None:
        # 일반 유저가 관리자용 엔드포인트 접근 시 403 응답 확인
        user = User.objects.create_user(
            email="user@test.com",
            password="1234",
            birthday=date(1995, 5, 5),
            nickname="일반유저",
            phone_number="01099998888",
        )
        self.client.force_authenticate(user=user)
        url = reverse("admin_recruitment_list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
