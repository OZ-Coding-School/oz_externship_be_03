from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.studies.models.groups import StudyGroup
from apps.studies.models.notes import StudyNote


class StudyNoteCRUDRefactoredTestCase(APITestCase):
    """스터디 노트 CRUD 테스트 (리팩터링 이후 URL 구조 반영)"""

    def setUp(self) -> None:
        # 그룹은 여전히 존재해야 함 (study_group FK)
        self.group = StudyGroup.objects.create(
            name="테스트 그룹",
            introduction="Mock Group for StudyNote Test",
            max_headcount=5,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=30),
            status="PENDING",
        )
        self.list_url = reverse("studies:study-note-list-create")

    def test_create_and_retrieve_study_note(self) -> None:
        """노트 생성 후 목록 및 단일 조회"""
        payload = {
            "title": "DRF 학습",
            "content": "APIView, Serializer 차이점 정리",
            "study_group": self.group.id,
        }

        # ✅ 생성
        res_create = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        note_id = res_create.json()["data"]["id"]

        # ✅ 목록 조회
        res_list = self.client.get(self.list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertTrue(any(n["id"] == note_id for n in res_list.json()["data"]))

        # ✅ 단일 조회
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note_id})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.json()["data"]["id"], note_id)

    def test_update_and_delete_study_note(self) -> None:
        """노트 수정 및 삭제"""
        note = StudyNote.objects.create(
            study_group=self.group,
            title="초기 제목",
            content="초기 내용",
        )
        detail_url = reverse("studies:study-note-detail", kwargs={"note_id": note.id})

        # ✅ 수정 (PATCH)
        res_patch = self.client.patch(detail_url, {"title": "수정된 제목"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.json()["data"]["title"], "수정된 제목")

        # ✅ 삭제
        res_delete = self.client.delete(detail_url)
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(StudyNote.objects.filter(id=note.id).exists())
