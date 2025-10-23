import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.lecture.models import (
    Category,
    CrawledLecture,
    CrawledLectureReview,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)

User = get_user_model()


class RecommendationAPIViewIntegrationTest(APITestCase):
    def setUp(self) -> None:
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
        self.url = reverse("recommendations")

        # 카테고리 생성
        self.categories = [Category.objects.create(name=f"카테고리 {i}") for i in range(3)]

        # 강의 생성 및 카테고리 할당
        self.lectures = []
        for i in range(5):
            lec = CrawledLecture.objects.create(
                uuid=str(uuid.uuid4()),
                title=f"테스트 강의 {i}",
                instructor=f"강사 {i}",
                thumbnail_img_url=f"https://mock.com/thumb{i}.jpg",
                difficulty="NORMAL",
                original_price=100000,
                discount_price=80000,
                platform="INFLEARN",
                average_rating=4.5,
                duration=120,
                url_link=f"https://mock.com/course/{i}",
                description="테스트용 설명",
            )
            LectureCategory.objects.create(lecture=lec, category=self.categories[i % 3])
            self.lectures.append(lec)

        # 행동 데이터 생성
        LectureBookmark.objects.create(user=self.user, lecture=self.lectures[0])
        LectureSearchLog.objects.create(user=self.user, keyword="테스트")
        UserPreferCategory.objects.create(user=self.user, category=self.categories[0])
        CrawledLectureReview.objects.create(lecture=self.lectures[0], rating="5_OUT_OF_5_STARS")

    def test_recommendations_api_returns_expected_data(self) -> None:
        # API 호출 성공 여부 검증
        # 응답 데이터 내 필수 키 존재 확인
        # 추천 결과가 리스트 타입인지 확인
        # 추천 강의 항목에 예상 필드 전부 존재하는지 확인
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        self.assertIn("data", response.data)
        self.assertIn("recommendations", response.data["data"])

        recs = response.data["data"]["recommendations"]
        self.assertIsInstance(recs, list)

        if recs:
            expected_keys = {
                "id",
                "uuid",
                "title",
                "instructor",
                "thumbnail_img_url",
                "categories",
                "difficulty",
                "original_price",
                "discount_price",
                "platform",
                "average_rating",
                "url_link",
                "is_bookmarked",
            }
            self.assertTrue(expected_keys.issubset(recs[0].keys()))

    def test_recommendations_api_requires_authentication(self) -> None:
        # 인증 해제 상태에서 API 호출 시 401 응답 확인
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
