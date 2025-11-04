from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.recruitments.models.bookmark import Bookmark
from apps.recruitments.models.recruitments import Recruitment
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class BookmarkAPITestCase(APITestCase):
    """Bookmark CRUD API 실제 DB 기반 테스트"""

    def setUp(self) -> None:
        # 테스트 유저 생성
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            birthday=date(2000, 1, 1),
        )

        # 로그인 상태 유지
        self.client.force_authenticate(user=self.user)

        now = timezone.now()

        # 스터디 그룹 생성
        self.study_group = StudyGroup.objects.create(
            name="테스트 스터디그룹",
            introduction="테스트 설명",
            max_headcount=5,
            start_at=now,
            end_at=now + timedelta(days=7),
        )

        # 그룹 리더 등록
        self.group_leader = GroupMember.objects.create(
            study_group=self.study_group,
            user=self.user,
            is_leader=True,
        )

        # 모집글 생성
        self.recruitment = Recruitment.objects.create(
            study_group=self.study_group,
            author=self.user,
            title="테스트 모집글",
            content="테스트용입니다.",
            estimated_fee=10000,
            expected_headcount=5,
            close_at=now + timedelta(days=7),
        )

        # ✅ 실제 엔드포인트 기반으로 수정
        self.list_url = "/api/v1/recruitments/bookmark/"
        self.detail_url = lambda uuid: f"/api/v1/recruitments/bookmark/{uuid}/"

        # 미리 북마크 하나 생성
        self.bookmark = Bookmark.objects.create(user=self.user, recruitment=self.recruitment)

    def test_create_bookmark_success(self) -> None:
        """북마크 생성 성공"""
        new_recruitment = Recruitment.objects.create(
            study_group=self.study_group,
            author=self.user,
            title="새 테스트 모집글",
            content="설명 내용",
            estimated_fee=10000,
            expected_headcount=5,
            close_at=timezone.now() + timedelta(days=3),
        )

        data = {"recruitment_id": new_recruitment.id}
        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Bookmark.objects.count(), 2)

        bookmark = Bookmark.objects.last()
        assert bookmark is not None
        self.assertEqual(bookmark.recruitment, new_recruitment)

    def test_create_bookmark_duplicate(self) -> None:
        """이미 북마크한 모집글 중복 요청 시 실패"""
        data = {"recruitment_id": self.recruitment.id}
        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 북마크한 모집글입니다.", str(response.data))

    def test_create_bookmark_invalid_recruitment(self) -> None:
        """존재하지 않는 recruitment_id 요청 시 실패"""
        data = {"recruitment_id": 9999}
        response = self.client.post(self.list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("존재하지 않는 모집글입니다.", str(response.data))

    def test_get_bookmark_list(self) -> None:
        """현재 유저의 북마크 목록 조회"""
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), Bookmark.objects.filter(user=self.user).count())
        self.assertIn("recruitment", response.data[0])

    def test_delete_bookmark_success(self) -> None:
        """북마크 삭제 성공"""
        # ✅ 실제 URL 네임스페이스 반영
        url = f"/api/v1/recruitments/bookmark/{self.bookmark.uuid}/"
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Bookmark.objects.filter(uuid=self.bookmark.uuid).exists())

    def test_delete_bookmark_not_found(self) -> None:
        """존재하지 않는 북마크 삭제 시 404"""
        import uuid

        invalid_uuid = uuid.uuid4()
        url = f"/api/v1/recruitments/bookmark/{invalid_uuid}/"
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("찾을 수 없습니다", str(response.data))
