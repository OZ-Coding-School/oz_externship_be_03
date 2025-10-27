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
        self.user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            nickname="ozdev",
            name="홍길동",
            phone_number="01012345678",
            birthday="1998-01-23",
            is_active=True,
        )

        # JWT 토큰 발급
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        # 토큰 출력 (인증 확인용)
        print("Access Token:", self.access_token)

        # 인증 헤더 설정
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_me_success(self) -> None:
        """
        로그인한 사용자가 /api/v1/me 조회 성공
        """
        url = reverse("users:me")  # 앱 네임스페이스 포함
        response = self.client.get(url)

        # 인증 확인 로그 (선택)
        print("Response status:", response.status_code)
        print("Response data:", response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["email"], self.user.email)
        self.assertEqual(response.data["data"]["nickname"], self.user.nickname)
        self.assertEqual(response.data["data"]["name"], self.user.name)

    def test_me_unauthorized(self) -> None:
        """
        인증되지 않은 요청은 401 반환
        """
        self.client.credentials()  # 인증 헤더 제거
        url = reverse("users:me")  # 앱 네임스페이스 포함
        response = self.client.get(url)

        # 인증 실패 로그 (선택)
        print("Unauthorized response status:", response.status_code)
        print("Unauthorized response data:", response.data)

        self.assertEqual(response.status_code, 401)
