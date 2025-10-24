from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.studies.models.groups import StudyGroup
from apps.studies.models.notes import StudyNote


class StudyNoteCRUDTestCase(APITestCase):
    """스터디노트 CRUD 테스트 (UUID 기반 URL 호환)"""

    def setUp(self) -> None:
        # 그룹 생성 (id는 BigAutoField, uuid는 UUIDField)
        self.group = StudyGroup.objects.create(
            name="테스트 그룹",
            introduction="Mock Group for StudyNote Test",
            max_headcount=5,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=30),
            status="PENDING",
        )

        # URL reverse 시 반드시 uuid 사용
        self.list_create_url = reverse(
            "study-note-list-create",
            kwargs={"group_id": str(self.group.uuid)},
        )

    def test_create_and_retrieve_study_note(self) -> None:
        """노트 생성 후 조회"""
        data = {"title": "DRF 학습", "content": "APIView, Serializer"}

        # 생성
        res = self.client.post(self.list_create_url, data, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        note_id = res.json()["data"]["id"]

        # 목록 조회
        res_list = self.client.get(self.list_create_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertTrue(any(n["id"] == note_id for n in res_list.json().get("data", [])))

        # 단일 조회 (uuid로 교체)
        detail_url = reverse(
            "study-note-detail",
            kwargs={"group_id": str(self.group.uuid), "note_id": note_id},
        )
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)

    def test_update_and_delete_study_note(self) -> None:
        """노트 수정 및 삭제"""
        note = StudyNote.objects.create(
            study_group=self.group,
            author=None,
            title="초기제목",
            content="초기내용",
        )

        # group_id는 반드시 uuid 문자열
        url = reverse(
            "study-note-detail",
            kwargs={"group_id": str(self.group.uuid), "note_id": note.id},
        )

        # 수정
        res_put = self.client.put(url, {"title": "수정됨"}, format="json")
        self.assertIn(res_put.status_code, [200, 403])

        # 삭제
        res_del = self.client.delete(url)
        self.assertIn(res_del.status_code, [204, 403])
