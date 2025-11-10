import random
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.recruitments.models import Application, ApplicationStatus, Recruitment
from apps.recruitments.views.admin_application_views import OrderingEnum
from apps.studies.models import StudyGroup
from apps.studies.models.groups import GroupMember
from apps.users.models import User


class AdminApplicationAPITestCase(APITestCase):
    admin_user: User
    applications: list[Application]
    search_keyword: str = "search"

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_user = User.objects.create_superuser(
            email=f"admin@example.com",
            nickname=f"admin",
            name=f"admin",
            birthday="2000-01-01",
            gender="M",
            phone_number=f"01011111111",
            password="password123",
        )

        other_users = [
            User(
                email=f"test{i}@example.com",
                nickname=f"test{i}",
                name=f"test{i}",
                birthday="2000-01-01",
                gender="M",
                phone_number=f"010000000{i}",
                password="password123",
                is_active=True,
                is_superuser=False,
                is_staff=False,
            )
            for i in range(1, 11)
        ]
        other_users = User.objects.bulk_create(other_users)

        study_groups = [
            StudyGroup(
                name=f"test{i}",
                max_headcount=i % 2,
                introduction=f"test_study_group{i}",
                start_at=timezone.now(),
                end_at=timezone.now() + timedelta(days=100),
            )
            for i in range(1, 11)
        ]
        study_groups = StudyGroup.objects.bulk_create(study_groups)

        group_leaders = [
            GroupMember(
                user=u,
                study_group=g,
                is_leader=True,
            )
            for u, g in zip(other_users, study_groups)
        ]
        GroupMember.objects.bulk_create(group_leaders)

        recruitments = [
            Recruitment(
                author=u,
                study_group=g,
                title=f"{g.name} recruitment" if g.pk != 9 else f"{g.name} for {cls.search_keyword}",
                content="content",
                close_at=timezone.now() + timedelta(days=10),
                is_closed=False,
                estimated_fee=10000,
                expected_headcount=5,
                views_count=10,
            )
            for u, g in zip(other_users, study_groups)
        ]
        recruitments = Recruitment.objects.bulk_create(recruitments)

        applications = [
            Application(
                recruitment=r,
                user=u,
                status=random.choice(ApplicationStatus.values),
                self_introduction=f"나는 {u.name} 입니다.",
                available_time="10:00 ~ 18:00",
                motivation=f"{r.study_group.name}을 위해 지원함.",  # type: ignore
                has_study_experience=False,
                study_experience="",
            )
            for u in other_users
            for r in recruitments
            if not r.study_group.group_members.filter(user=u).exists()  # type: ignore
        ]
        cls.applications = Application.objects.bulk_create(applications)

    def setUp(self) -> None:
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_application_list_success_without_query_params(self) -> None:
        url = reverse("admin-application-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["count"], len(self.applications))

    def test_admin_application_list_success_with_search_query_param(self) -> None:
        url = reverse("admin-application-list")

        response = self.client.get(url, query_params={"keyword": self.search_keyword})
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertEqual(len(response.data["results"]), 9)

    def test_admin_application_list_success_with_ordering_query_param(self) -> None:
        url = reverse("admin-application-list")

        response = self.client.get(url, query_params={"ordering": OrderingEnum.LATEST})
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(
            response.data["results"][0]["id"],
            Application.objects.all().order_by("-created_at").first().id,  # type: ignore
        )

    def test_admin_application_list_success_with_status_query_param(self) -> None:
        url = reverse("admin-application-list")

        response = self.client.get(url, query_params={"status": ApplicationStatus.PENDING})
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        for data in response.data["results"]:
            self.assertEqual(data["status"], ApplicationStatus.PENDING)

    def test_admin_application_list_success_with_pagination_query_params(self) -> None:
        url = reverse("admin-application-list")
        response = self.client.get(url, query_params={"limit": (limit := 20), "offset": (offset := 20)})

        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(len(response.data["results"]), limit)
        self.assertEqual(response.data["count"], len(self.applications))
        self.assertEqual(
            response.data["results"][0]["id"],
            Application.objects.all().order_by("-created_at").first().id - offset,  # type: ignore
        )

    def test_admin_application_list_failed_with_user_role(self) -> None:
        user = User.objects.create(
            email=f"user@example.com",
            nickname=f"user",
            name=f"user",
            birthday="2000-01-01",
            gender="M",
            phone_number=f"01033333333",
            password="password123",
            is_active=True,
            is_superuser=False,
            is_staff=False,
        )
        url = reverse("admin-application-list")
        self.client.force_authenticate(user=user)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_application_detail_success(self) -> None:
        url = reverse("admin-application-detail", kwargs={"application_id": self.applications[0].pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("id", response.data)
        self.assertIn("user", response.data)
        self.assertIn("recruitment", response.data)
        self.assertIn("status", response.data)
        self.assertIn("self_introduction", response.data)
        self.assertIn("available_time", response.data)
        self.assertIn("motivation", response.data)
        self.assertIn("objective", response.data)
        self.assertIn("has_study_experience", response.data)
        self.assertIn("study_experience", response.data)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)
        self.assertEqual(response.data["id"], self.applications[0].pk)
        self.assertEqual(response.data["user"]["id"], self.applications[0].user.pk)
        self.assertEqual(response.data["recruitment"]["id"], self.applications[0].recruitment.pk)
        self.assertEqual(response.data["status"], self.applications[0].status)
        self.assertEqual(response.data["self_introduction"], self.applications[0].self_introduction)
        self.assertEqual(response.data["available_time"], self.applications[0].available_time)
        self.assertEqual(response.data["motivation"], self.applications[0].motivation)
        self.assertEqual(response.data["objective"], self.applications[0].objective)
        self.assertEqual(response.data["has_study_experience"], self.applications[0].has_study_experience)
        self.assertEqual(response.data["study_experience"], self.applications[0].study_experience)
        self.assertEqual(
            response.data["created_at"], timezone.localtime(self.applications[0].created_at).strftime("%Y-%m-%d %H:%M")
        )
        self.assertEqual(
            response.data["updated_at"], timezone.localtime(self.applications[0].updated_at).strftime("%Y-%m-%d %H:%M")
        )

    def test_admin_application_detail_failed_with_user_role(self) -> None:
        user = User.objects.create(
            email=f"user@example.com",
            nickname=f"user",
            name=f"user",
            birthday="2000-01-01",
            gender="M",
            phone_number=f"01033333333",
            password="password123",
            is_active=True,
            is_superuser=False,
            is_staff=False,
        )
        url = reverse("admin-application-detail", kwargs={"application_id": self.applications[0].pk})
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_application_detail_failed_with_invalid_application_id(self) -> None:
        url = reverse("admin-application-detail", kwargs={"application_id": 2121212312})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
