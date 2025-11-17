from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.recruitments.models import Application, Recruitment
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class ApplicationAPITest(APITestCase):
    """지원 내역 관리 API 테스트"""

    def setUp(self) -> None:
        """테스트 데이터 초기 설정"""
        # 사용자 생성
        self.author = User.objects.create_user(
            email="author@test.com",
            password="password123",
            nickname="작성자",
            name="작성자",
            phone_number="01012345678",
            birthday="1990-01-01",
            gender="MALE",
        )
        self.applicant = User.objects.create_user(
            email="applicant@test.com",
            password="password123",
            nickname="지원자",
            name="지원자",
            phone_number="01087654321",
            birthday="1995-01-01",
            gender="FEMALE",
        )
        self.other_user = User.objects.create_user(
            email="other@test.com",
            password="password123",
            nickname="다른유저",
            name="다른유저",
            phone_number="01011112222",
            birthday="1992-01-01",
            gender="MALE",
        )

        # 스터디 그룹 생성
        self.study_group = StudyGroup.objects.create(
            name="테스트 스터디",
            max_headcount=5,
            start_at="2025-01-01T00:00:00Z",
            end_at="2025-12-31T23:59:59Z",
        )

        # 공고 생성
        self.recruitment = Recruitment.objects.create(
            author=self.author,
            study_group=self.study_group,
            title="테스트 공고",
            content="테스트 내용",
            estimated_fee=100000,
            expected_headcount=3,
        )

        # 지원 내역 생성
        self.application = Application.objects.create(
            recruitment=self.recruitment,
            user=self.applicant,
            self_introduction="자기소개",
            motivation="지원동기",
            objective="목표",
            available_time="평일 저녁",
            has_study_experience=True,
            study_experience="이전 스터디 경험",
        )

    def test_list_applications_success(self) -> None:
        """지원 내역 목록 조회 성공"""
        self.client.force_authenticate(user=self.author)
        url = reverse("recruitments:application-list", kwargs={"recruitment_uuid": self.recruitment.uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["applicant"]["nickname"], "지원자")

    def test_list_applications_permission_denied(self) -> None:
        """지원 내역 목록 조회 권한 실패"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("recruitments:application-list", kwargs={"recruitment_uuid": self.recruitment.uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_application_success(self) -> None:
        """지원 내역 상세 조회 성공"""
        self.client.force_authenticate(user=self.author)
        url = reverse("recruitments:application-detail", kwargs={"application_uuid": self.application.uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["applicant"]["nickname"], "지원자")
        self.assertEqual(response.data["motivation"], "지원동기")

    def test_approve_application_success(self) -> None:
        """지원 승인 성공"""
        self.client.force_authenticate(user=self.author)
        url = reverse("recruitments:application-approve", kwargs={"application_uuid": self.application.uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "APPROVED")
        self.assertTrue(GroupMember.objects.filter(study_group=self.study_group, user=self.applicant).exists())

    def test_approve_application_already_processed(self) -> None:
        """이미 처리된 지원 승인 실패"""
        self.application.status = "APPROVED"
        self.application.save()

        self.client.force_authenticate(user=self.author)
        url = reverse("recruitments:application-approve", kwargs={"application_uuid": self.application.uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_application_success(self) -> None:
        """지원 거절 성공"""
        self.client.force_authenticate(user=self.author)
        url = reverse("recruitments:application-reject", kwargs={"application_uuid": self.application.uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "REJECTED")

    def test_reject_application_permission_denied(self) -> None:
        """지원 거절 권한 실패"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("recruitments:application-reject", kwargs={"application_uuid": self.application.uuid})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
