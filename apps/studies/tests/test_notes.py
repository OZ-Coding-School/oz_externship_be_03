from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.studies.models.groups import GroupMember, StudyGroup
from apps.studies.models.notes import StudyNote


class StudyNoteCRUDRefactoredTestCase(APITestCase):
    """
    ✅ StudyNote CRUD 통합 테스트
    """

    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="test1234",
            name="테스트유저",
            nickname="tester",
            phone_number="01012345678",
            gender="MALE",
            birthday=date(1999, 1, 1),
        )

        self.group = StudyGroup.objects.create(
            name="테스트 스터디그룹",
            introduction="테스트용 그룹입니다.",
            max_headcount=5,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=7),
            status="PENDING",
        )

        GroupMember.objects.create(
            study_group=self.group,
            user=self.user,
            is_leader=True,
        )

        self.client.force_authenticate(user=self.user)

        # ✅ URL 분리
        self.create_url = reverse("studies:study-note-create")
        self.list_url = reverse("studies:study-note-list", kwargs={"group_id": self.group.uuid})


    # ----------------------------------------------------------------------

    def test_create_and_retrieve_study_note(self) -> None:
        """✅ 노트 생성 → 목록 → 상세 조회"""
        payload = {
            "title": "Django REST Framework 학습",
            "content": "APIView와 GenericAPIView 차이점 정리",
            "group_uuid": str(self.group.uuid),
        }

        # ▶ 생성
        res_create = self.client.post(self.create_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED, res_create.json())
        note_id = res_create.json()["data"]["id"]

        # ▶ 목록 조회
        res_list = self.client.get(self.list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK, res_list.json())
        self.assertTrue(any(n["id"] == note_id for n in res_list.json()["data"]))

        # ▶ 상세 조회
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note_id})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.json()["data"]["id"], note_id)

    # ----------------------------------------------------------------------

    def test_update_and_delete_study_note(self) -> None:
        """✅ 노트 수정 및 삭제"""
        note = StudyNote.objects.create(
            study_group=self.group,
            author=self.user,
            title="초기 제목",
            content="초기 내용",
        )

        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})

        res_patch = self.client.patch(detail_url, {"title": "수정된 제목"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK, res_patch.json())
        self.assertEqual(res_patch.json()["data"]["title"], "수정된 제목")

        res_delete = self.client.delete(detail_url)
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(StudyNote.objects.filter(id=note.id).exists())
