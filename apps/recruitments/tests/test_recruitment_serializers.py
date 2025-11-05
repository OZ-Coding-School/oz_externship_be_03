from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.recruitment_serializers import (
    RecruitmentDetailSerializer,
)


class RecruitmentDetailSerializerTest(TestCase):
    """RecruitmentDetailSerializer 테스트"""

    def test_recruitment_detail_serializer(self) -> None:
        """RecruitmentDetailSerializer가 공고 데이터를 올바르게 직렬화하는지 테스트"""

        #  테스트용 유저 생성 (birthday 포함)
        User = get_user_model()
        user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
            name="테스트유저",
            birthday=date(2000, 1, 1),
        )

        #  Recruitment 생성 시 author 지정
        recruitment = Recruitment.objects.create(
            author=user,
            title="테스트 공고",
            content="내용",
            estimated_fee=10000,
            expected_headcount=5,
            views_count=10,
            close_at="2025-12-31T00:00:00Z",  # UTC timezone aware로 설정
            is_closed=False,
        )

        serializer = RecruitmentDetailSerializer(recruitment)
        data = serializer.data

        self.assertEqual(data["title"], "테스트 공고")
        self.assertIn("tags", data)
