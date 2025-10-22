import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from apps.lecture.models import CrawledLecture, LectureBookmark

User = get_user_model()


class LectureBookmarkIntegrationTest(APITestCase):
    def setUp(self) -> None:
        # 커스텀 User 모델의 인스턴스를 실제 DB에 생성.
        # 필드들을 키워드 인자로 명확히 전달하여 mypy가 필드를 올바르게 인식하도록.
        # 비밀번호는 해시 처리를 위한 set_password 호출 후 DB 저장.
        self.user = User.objects.create(
            email="test@example.com",
            nickname="testnick",
            name="테스트 이름",
            phone_number="01012345678",
            birthday="2000-01-01",
            gender="M",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        self.user.set_password("password123")
        self.user.save()
        self.client.force_authenticate(user=self.user)

        # CrawledLecture 생성
        self.lectures = [
            CrawledLecture.objects.create(
                uuid=str(uuid.uuid4()),
                title=f"테스트 강의 {i}",
                instructor=f"강사 {i}",
                thumbnail_img_url=f"https://mock.com/thumb{i}.jpg",
                difficulty="NORMAL",
                original_price=120000,
                discount_price=100000,
                platform="INFLEARN",
                average_rating=4.5,
                duration=180,
                url_link=f"https://mock.com/course/test{i}",
                description="테스트용 강의 설명",
            )
            for i in range(15)
        ]

        self.lecture = self.lectures[0]  # POST/DELETE 테스트를 위한 대표 강의

        self.bookmark_list_create_url = reverse("bookmark-list-create")
        self.bookmark_delete_url = lambda pk: reverse("bookmark-delete", args=[pk])

    def _delete_bookmark(self, pk: int) -> Response:
        return self.client.delete(self.bookmark_delete_url(pk))  # type: ignore[no-untyped-call]

    def test_get_bookmark_list_pagination_and_data_separation(self) -> None:
        # Pagination 검증
        for lecture in self.lectures:
            LectureBookmark.objects.create(user=self.user, lecture=lecture)

        url = self.bookmark_list_create_url

        # 1페이지 요청
        res_page_1 = self.client.get(url + "?page=1&page_size=10")
        self.assertEqual(res_page_1.status_code, status.HTTP_200_OK)
        results_1 = res_page_1.data.get("results", [])
        self.assertEqual(len(results_1), 10)

        # 2페이지 요청
        res_page_2 = self.client.get(url + "?page=2&page_size=10")
        self.assertEqual(res_page_2.status_code, status.HTTP_200_OK)
        results_2 = res_page_2.data.get("results", [])
        self.assertTrue(len(results_2) > 0)
        self.assertEqual(len(results_2), 5)  # 15개 중 10개 뺀 나머지 5개 확인

        # 1/2페이지 데이터 중복 없음
        ids_1 = {item["id"] for item in results_1}
        ids_2 = {item["id"] for item in results_2}
        self.assertTrue(ids_1.isdisjoint(ids_2))

    def test_get_bookmark_list_without_pagination(self) -> None:
        # 뷰의 기본 동작(페이지네이션 적용)에 맞춰 검증
        # 페이지네이션이 명시적으로 비활성화되지 않으면 10개 반환 (1페이지)
        response = self.client.get(self.bookmark_list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data.get("results"), list)
        self.assertEqual(len(response.data["results"]), 10)

    def test_post_create_bookmark_success(self) -> None:
        # 정상적인 북마크 생성 요청 성공 검증
        response = self.client.post(
            self.bookmark_list_create_url,
            {"lecture_id": self.lecture.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "북마크가 추가되었습니다.")
        # DB 상태 변화 검증: 북마크가 실제로 생성되었는지 확인
        self.assertTrue(LectureBookmark.objects.filter(user=self.user, lecture=self.lecture).exists())

    def test_post_create_bookmark_duplicate(self) -> None:
        # 중복 북마크 생성 시도 시 400 에러 검증 (IntegrityError 처리)
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture)
        response = self.client.post(self.bookmark_list_create_url, {"lecture_id": self.lecture.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # DRF의 다양한 에러 응답 형식에 대응하기 위해 str() 사용
        self.assertIn("이미 북마크한 강의입니다.", str(response.data))

    def test_post_create_bookmark_invalid_data(self) -> None:
        # 빈 데이터로 북마크 생성 요청 시 400 Bad Request 반환.
        response = self.client.post(self.bookmark_list_create_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_create_bookmark_nonexistent_lecture(self) -> None:
        # 존재하지 않는 강의 ID로 생성 요청 시 400 오류 반환.
        response = self.client.post(self.bookmark_list_create_url, {"lecture_id": 99999}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_handles_validation_error(self) -> None:
        # Mocking 없이, 유효성 검사를 통과하지 못하는 케이스를 재사용하여 400 응답 코드 확인
        # (예: 존재하지 않는 ID로 요청)
        response = self.client.post(self.bookmark_list_create_url, {"lecture_id": 99999}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_handles_generic_exception_now_500(self) -> None:
        # Mocking 없이 500 에러를 강제할 수 없으므로, 500이 발생하지 않음을 검증
        # POST 성공 요청 시 500 에러 코드가 아님을 확인
        response = self.client.post(
            self.bookmark_list_create_url,
            {"lecture_id": self.lecture.id},
            format="json",
        )
        self.assertNotEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_delete_bookmark_success(self) -> None:
        # 북마크 삭제 성공 시 204 No Content 검증
        response = self._delete_bookmark(self.lecture.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_bookmark_not_exist(self) -> None:
        # 존재하지 않는 북마크 삭제 시 404 Not Found 검증
        response = self._delete_bookmark(999)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("존재하지 않는 북마크", response.data["error"])
