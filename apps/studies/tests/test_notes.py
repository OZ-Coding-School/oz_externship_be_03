from datetime import date, timedelta
from unittest.mock import MagicMock, patch

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
        self.list_url = reverse("studies:study-note-list", kwargs={"group_uuid": self.group.uuid})

    # ----------------------------------------------------------------------

    def test_create_and_retrieve_study_note(self) -> None:
        """✅ 노트 생성 → 목록 → 상세 조회"""
        payload = {
            "title": "Django REST Framework 학습",
            "content": "APIView와 GenericAPIView 차이점 정리",
            "study_group": str(self.group.uuid),
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


class StudyNoteAISummaryTestCase(APITestCase):
    """
    ✅ AI 요약 Celery 태스크 호출 Mock 테스트
    """

    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            email="ai@test.com",
            password="test1234",
            nickname="aiuser",
            name="AI유저",
            phone_number="01099999999",
            gender="MALE",
            birthday=date(1999, 1, 1),
        )

        self.group = StudyGroup.objects.create(
            name="AI 테스트 그룹",
            introduction="AI 요약 기능 테스트용",
            max_headcount=5,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=3),
            status="ACTIVE",
        )

        GroupMember.objects.create(study_group=self.group, user=self.user, is_leader=True)
        self.client.force_authenticate(user=self.user)

        self.create_url = reverse("studies:study-note-create")

    # ----------------------------------------------------------------------

    @patch("apps.studies.tasks.generate_ai_summary_task.delay")
    def test_ai_summary_task_is_called_on_create(self, mock_delay: MagicMock) -> None:
        """✅ 노트 생성 시 AI 요약 태스크가 비동기로 호출되는지 확인"""
        payload = {
            "title": "테스트 노트",
            "content": "Gemini 모델 호출 테스트",
            "study_group": str(self.group.uuid),
        }

        res = self.client.post(self.create_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.json())

        # ✅ Celery 태스크가 호출되었는지 확인
        note_id = res.json()["data"]["id"]
        mock_delay.assert_called_once_with(note_id)

    # ----------------------------------------------------------------------

    @patch("apps.studies.tasks.generate_ai_summary_task.delay")
    def test_ai_summary_task_is_called_on_update(self, mock_delay: MagicMock) -> None:
        """✅ 노트 수정 시 content가 바뀌면 AI 요약 재생성 태스크 호출 확인"""
        note = StudyNote.objects.create(
            study_group=self.group,
            author=self.user,
            title="수정 전 제목",
            content="수정 전 내용",
        )

        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})
        res = self.client.patch(detail_url, {"content": "수정된 내용"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_delay.assert_called_once_with(note.id, force=True)
