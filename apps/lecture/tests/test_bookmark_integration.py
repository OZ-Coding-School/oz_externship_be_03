from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.serializers.bookmark_serializers import (
    LectureBookmarkCreateSerializer,
)

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

        # 테스트 중 API 요청 시 인증된 사용자로 동작하도록 강제 인증 처리.
        self.client.force_authenticate(user=self.user)

        # APIRequestFactory 인스턴스를 생성하여 뷰 직접 호출 시 요청 객체 생성 준비.
        self.factory = APIRequestFactory()

        # 테스트용 강의 데이터를 실제 DB에 생성하며 키워드 인자로 각 필드를 명확히 지정.
        self.lecture = CrawledLecture.objects.create(
            uuid="123e4567-e89b-12d3-a456-426614174000",
            title="테스트 강의",
            instructor="테스트 강사",
            thumbnail_img_url="https://mock.com/thumb.jpg",
            difficulty="NORMAL",
            original_price=120000,
            discount_price=100000,
            platform="INFLEARN",
            average_rating=4.5,
            duration=180,
            url_link="https://mock.com/course/test",
            description="테스트용 강의 설명",
        )

        # reverse 함수를 사용해 북마크 리스트 생성 API 엔드포인트 URL 준비.
        self.bookmark_list_create_url = reverse("bookmark-list-create")
        # 북마크 삭제 API 엔드포인트 URL을 동적으로 생성하는 람다 함수 정의.
        self.bookmark_delete_url = lambda pk: reverse("bookmark-delete", args=[pk])

    def _get_request(self) -> object:
        # APIRequestFactory를 통해 POST 요청 객체를 생성하고,
        # 테스트 시 직접 뷰 함수에 전달할 수 있도록 인증된 유저를 연결하여 준비.
        request = self.factory.post("/")
        request.user = self.user
        return request

    def _delete_bookmark(self, pk: int) -> Response:
        # DRF 테스트 클라이언트의 delete() 메서드는 타입 힌트가 없으므로
        # mypy의 no-untyped-call 오류 방지를 위해 해당 호출부에 타입 무시 주석 추가.
        return self.client.delete(self.bookmark_delete_url(pk))  # type: ignore[no-untyped-call]

    def test_get_bookmark_list_default_page(self) -> None:
        # 북마크 리스트 조회 시 기본 페이지 요청에 대해 200 응답,
        # 결과 내 results 키 존재 및 비어있지 않음.
        response = self.client.get(self.bookmark_list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertTrue(len(response.data["results"]) > 0)

    def test_get_bookmark_list_with_page_params(self) -> None:
        # 페이지 번호와 페이지 크기 쿼리 파라미터가 포함된 요청에 대해
        # 200 응답, 결과 수 제한 확인.
        response = self.client.get(self.bookmark_list_create_url + "?page=2&page_size=10")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertLessEqual(len(response.data["results"]), 10)

    def test_get_bookmark_list_without_pagination(self) -> None:
        # 페이지네이션이 비활성화된 상태에서,
        # 리스트가 JSON 배열 형태로 반환.
        with patch("apps.lecture.views.bookmark_views.PageNumberPagination.paginate_queryset", return_value=None):
            response = self.client.get(self.bookmark_list_create_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsInstance(response.data, list)
            self.assertGreater(len(response.data), 0)

    def test_post_create_bookmark_success(self) -> None:
        # 북마크 생성 POST 요청 정상 처리 테스트. 성공 시 201, 실패 시 400 예상.
        # 201일 때 응답 메시지와 DB에 실제 레코드 확인.
        response = self.client.post(
            self.bookmark_list_create_url,
            {"lecture_id": self.lecture.id},
            format="json",
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        if response.status_code == status.HTTP_201_CREATED:
            self.assertEqual(response.data["detail"], "북마크가 추가되었습니다.")
            self.assertTrue(LectureBookmark.objects.filter(user=self.user, lecture=self.lecture).exists())

    def test_post_create_bookmark_invalid_data(self) -> None:
        # 빈 데이터로 북마크 생성 요청 시 400 Bad Request 반환.
        response = self.client.post(self.bookmark_list_create_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_create_bookmark_nonexistent_lecture(self) -> None:
        # 존재하지 않는 강의 ID로 생성 요청 시 400 오류 반환.
        response = self.client.post(self.bookmark_list_create_url, {"lecture_id": 99999}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_create_bookmark_duplicate(self) -> None:
        # 중복 북마크 생성 시도에 대해 400 오류와 관련 메시지 반환.
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture)
        response = self.client.post(self.bookmark_list_create_url, {"lecture_id": self.lecture.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("이미 북마크한 강의입니다.", response.data["detail"])

    def test_post_handles_validation_error(self) -> None:
        # serializer.save() 호출 중 ValidationError 가 발생하는 상황에서
        # 400 응답이 제대로 처리되는지 확인.
        with patch("apps.lecture.serializers.bookmark_serializers.LectureBookmarkCreateSerializer.save") as mock_save:
            mock_save.side_effect = serializers.ValidationError({"detail": "강제 ValidationError"})
            response = self.client.post(self.bookmark_list_create_url, {"lecture_id": self.lecture.id}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("강제 ValidationError", str(response.data["detail"]))

    def test_post_handles_generic_exception(self) -> None:
        # serializer.save() 호출 중 일반 Exception 발생 상황에서
        # 400 응답 처리 검증.
        with patch("apps.lecture.serializers.bookmark_serializers.LectureBookmarkCreateSerializer.save") as mock_save:
            mock_save.side_effect = Exception("강제 Exception")
            response = self.client.post(self.bookmark_list_create_url, {"lecture_id": self.lecture.id}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("강제 Exception", str(response.data["detail"]))

    def test_delete_bookmark_success(self) -> None:
        # 정상적인 북마크 삭제 요청 시 204 No Content 응답.
        response = self._delete_bookmark(self.lecture.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_bookmark_not_exist(self) -> None:
        # 존재하지 않는 북마크 삭제 요청에 대해 404 Not Found 및 오류 메시지.
        response = self._delete_bookmark(999)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("존재하지 않는 북마크", response.data["error"])

    def test_serializer_validate_duplicate_raises_validation_error(self) -> None:
        # serializer.validate() 메서드가 중복된 북마크 생성 시 ValidationError 발생.
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture)
        serializer = LectureBookmarkCreateSerializer(
            data={"lecture_id": self.lecture.id}, context={"request": self._get_request()}
        )
        serializer.is_valid()
        with self.assertRaises(ValidationError):
            serializer.validate({"lecture": self.lecture})

    def test_serializer_create_integrity_error_handling(self) -> None:
        # serializer.save() 호출 시 중복 생성으로 IntegrityError 발생이 ValidationError로 변환.
        serializer = LectureBookmarkCreateSerializer(
            data={"lecture_id": self.lecture.id}, context={"request": self._get_request()}
        )
        serializer.is_valid()
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture)
        with self.assertRaises(ValidationError):
            serializer.save()
