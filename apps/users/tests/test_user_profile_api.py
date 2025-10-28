from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class MeAPITest(APITestCase):
    def setUp(self) -> None:
        """
        테스트용 유저 생성 및 JWT 인증 설정
        """
        # 테스트용 유저 생성
        self.user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            nickname="ozdev",
            name="홍길동",
            phone_number="01012345678",
            birthday="1998-01-23",
            gender="M",
            is_active=True,
        )

        # JWT 토큰 발급
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        # 인증 헤더 설정
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_me_success(self) -> None:
        """
        로그인한 사용자가 /api/v1/me 조회 성공
        """
        url = reverse("users:me")
        response = self.client.get(url)

        # 검증
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["nickname"], self.user.nickname)
        self.assertEqual(response.data["name"], self.user.name)
        self.assertIn("profile_img_url", response.data)  # 필드 존재 확인
        self.assertIn("created_at", response.data)

    def test_me_unauthorized(self) -> None:
        """
        인증되지 않은 요청은 401 반환
        """
        self.client.credentials()  # 인증 헤더 제거
        url = reverse("users:me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "자격 인증데이터(authentication credentials)가 제공되지 않았습니다.")
