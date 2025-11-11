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

    def test_get_requires_authentication(self) -> None:
        """❌ 비로그인 사용자는 접근 불가"""
        self.client.logout()
        note = StudyNote.objects.create(study_group=self.group, author=self.user, title="테스트", content="내용")
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_forbidden_for_non_member(self) -> None:
        """❌ 그룹 미가입 사용자는 조회 불가 (403)"""
        User = get_user_model()
        outsider = User.objects.create_user(
            email="outsider@test.com",
            password="test1234",
            nickname="outsider",
            birthday=date(1999, 1, 1),
        )
        self.client.force_authenticate(user=outsider)
        note = StudyNote.objects.create(study_group=self.group, author=self.user, title="테스트", content="내용")
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_success_for_group_member(self) -> None:
        """✅ 그룹 멤버는 작성자가 아니어도 조회 가능"""
        User = get_user_model()
        member = User.objects.create_user(
            email="member@test.com",
            password="test1234",
            nickname="member",
            birthday=date(1999, 1, 1),
        )
        GroupMember.objects.create(study_group=self.group, user=member)
        note = StudyNote.objects.create(study_group=self.group, author=self.user, title="테스트", content="내용")
        self.client.force_authenticate(user=member)
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())

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
        """✅ 작성자는 노트를 수정 및 삭제 가능"""
        note = StudyNote.objects.create(
            study_group=self.group,
            author=self.user,
            title="초기 제목",
            content="초기 내용",
        )

        GroupMember.objects.get_or_create(study_group=self.group, user=self.user)
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})

        res_patch = self.client.patch(detail_url, {"title": "수정된 제목"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK, res_patch.json())
        self.assertEqual(res_patch.json()["data"]["title"], "수정된 제목")

        res_delete = self.client.delete(detail_url)
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(StudyNote.objects.filter(id=note.id).exists())

    def test_update_forbidden_for_non_author(self) -> None:
        """❌ 작성자가 아닌 멤버는 수정 불가"""
        User = get_user_model()
        other = User.objects.create_user(
            email="other@test.com",
            password="test1234",
            nickname="other",
            birthday=date(1999, 1, 1),
        )
        GroupMember.objects.create(study_group=self.group, user=other)
        note = StudyNote.objects.create(
            study_group=self.group,
            author=self.user,
            title="수정불가",
            content="내용",
        )
        self.client.force_authenticate(user=other)
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})
        res = self.client.patch(detail_url, {"title": "수정시도"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class StudyNoteAISummaryTestCase(APITestCase):
    """
    ✅ AI 요약 기능 관련 테스트 (동기 호출 기반)
    - 생성 시 summarize 호출
    - 수정 시 content 변경 시 summarize 재호출
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

        GroupMember.objects.get_or_create(study_group=self.group, user=self.user, is_leader=True)
        self.client.force_authenticate(user=self.user)
        self.create_url = reverse("studies:study-note-create")

    # ----------------------------------------------------------------------

    @patch("apps.studies.services.notes.StudyNoteAIService.summarize")
    def test_ai_summary_called_on_create(self, mock_summarize: MagicMock) -> None:
        """✅ 노트 생성 시 summarize가 호출되는지 확인"""
        payload = {
            "title": "테스트 노트",
            "content": "Gemini 모델 호출 테스트",
            "study_group": str(self.group.uuid),
        }

        res = self.client.post(self.create_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.json())

        # StudyNoteAIService.summarize가 호출되었는지 확인
        mock_summarize.assert_called_once()
        called_note = mock_summarize.call_args[0][0]
        self.assertIsInstance(called_note, StudyNote)

    # ----------------------------------------------------------------------

    @patch("apps.studies.services.notes.StudyNoteAIService.summarize")
    def test_ai_summary_called_on_update(self, mock_summarize: MagicMock) -> None:
        """✅ 노트 수정 시 content 변경 시 summarize 재호출"""
        note = StudyNote.objects.create(
            study_group=self.group,
            author=self.user,
            title="수정 전 제목",
            content="수정 전 내용",
        )

        GroupMember.objects.get_or_create(study_group=self.group, user=self.user)
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})
        res = self.client.patch(detail_url, {"content": "수정된 내용"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())

        mock_summarize.assert_called_once()
        called_note = mock_summarize.call_args[0][0]
        self.assertEqual(called_note.id, note.id)
