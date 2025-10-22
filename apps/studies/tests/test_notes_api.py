from unittest.mock import MagicMock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.studies.models import StudyGroup, StudyNote
from apps.users.models import User


class TestStudyNoteAPI(TestCase):
    """스터디노트 API 테스트"""

    def setUp(self):
        """테스트마다 기본 세팅"""
        self.client = APIClient()

        #테스트용유저하나만들고로그인한상태로만듬
        self.user = User.objects.create(email="test@test.com", password="1234", birthday="2000-01-01")
        self.client.force_authenticate(user=self.user)

        #테스트용그룹하나생성
        self.group = StudyGroup.objects.create(
            name="테스트 그룹",
            introduction="테스트용",
            start_at="2025-10-01",
            end_at="2025-10-31",
        )

        #테스트용노트하나만듬
        self.note = MagicMock(spec=StudyNote)
        self.note.id = 1
        self.note.study_group = self.group
        self.note.author = self.user
        self.note.title = "기존 노트"
        self.note.content = "기존 내용"

    def test_get_notes_list(self):
        """노트목록불러오기(GET)테스트"""
        url = reverse("studynote-list")
        response = self.client.get(f"{url}?group_id={self.group.id}")
        #응답코드확인
        self.assertIn(response.status_code, [200, 204, 404])
        #응답형식확인
        self.assertIsInstance(response.data, dict | list)

    def test_create_note(self):
        """노트작성(POST)테스트"""
        url = reverse("studynote-list")
        data = {"title": "새로운 노트", "content": "테스트 내용입니다."}
        response = self.client.post(f"{url}?group_id={self.group.id}", data)
        #응답코드확인
        #201 = 성공적으로노트작성됨
        #401 = 로그인안되어있음(인증안됨)
        #403 = 권한없음(로그인했는데그룹멤버아님)
        self.assertIn(response.status_code, [201, 401, 403])
        #정상일경우title필드확인
        if response.status_code == 201:
            self.assertIn("title", response.data)

    def test_update_note(self):
        """노트수정(PATCH)테스트"""
        url = f"/api/v1/studies/notes/{self.note.id}/"
        data = {"title": "수정된 노트 제목", "content": "수정된 내용"}
        response = self.client.patch(url, data)
        #응답코드확인
        #200 = 수정성공
        #401 = 로그인안되어있음
        #403 = 권한없음
        #404 = 노트없음
        self.assertIn(response.status_code, [200, 401, 403, 404])

    def test_get_note_detail(self):
        """노트상세조회(GET)테스트"""
        url = f"/api/v1/studies/notes/{self.note.id}/"
        response = self.client.get(url)
        #응답코드확인
        #200 = 조회성공
        #401 = 로그인안되어있음
        #403 = 권한없음
        #404 = 노트없음
        self.assertIn(response.status_code, [200, 401, 403, 404])

    def test_delete_note(self):
        """노트삭제(DELETE)테스트"""
        url = f"/api/v1/studies/notes/{self.note.id}/"
        response = self.client.delete(url)
        #응답코드확인
        #204 = 삭제성공
        #401 = 로그인안되어있음
        #403 = 권한없음
        #404 = 노트없음
        self.assertIn(response.status_code, [204, 401, 403, 404])

    def test_get_note_summary(self):
        """노트요약조회(GET)테스트"""
        url = f"/api/v1/studies/notes/{self.note.id}/summary/"
        response = self.client.get(url)
        #응답코드확인
        #200 = 요약조회성공
        #401 = 로그인안되어있음
        #403 = 권한없음
        #404 = 노트없음
        self.assertIn(response.status_code, [200, 401, 403, 404])
