from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import CrawledLecture
from apps.lecture.serializers.recommend_serializers import RecommendedLecturesDTO


class UserRecommendedLecturesAPIView(APIView):
    """사용자 맞춤 추천 강의 API 뷰"""

    permission_classes = [AllowAny]  # TODO: 기능 구현 후 권한 변경
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["Lectures"],
        summary="사용자 맞춤 추천 강의 조회 API (Mock 데이터)",
        responses={200: RecommendedLecturesDTO},
    )
    def get(self, request: Request) -> Response:
        # 임시로 Mock 강의 객체 1개 생성
        mock_lecture = CrawledLecture(
            id=1,
            uuid="123e4567-e89b-12d3-a456-426614174000",
            title="Mock 추천 강의",
            instructor="홍길동",
            thumbnail_img_url="https://example.com/thumb-python.jpg",
            difficulty="NORMAL",
            original_price=120000,
            discount_price=100000,
            platform="inflearn",
            average_rating=4.6,
            duration=90,
            url_link="https://inflearn.com/course/mock",
            description="기초부터 배우는 파이썬",
        )

        # 반환할 JSON에 포함할 데이터 구성
        data_for_serialization = {
            "nickname": "홍길동",
            "recommendations": [mock_lecture] * 3,
        }

        # DTO용 시리얼라이저로 유효성 검사 및 직렬화 처리 위임
        serializer = RecommendedLecturesDTO(data=data_for_serialization)
        serializer.is_valid(raise_exception=True)
        response_data = {
            "detail": "맞춤 강의 추천 조회가 완료되었습니다.",
            "data": serializer.data,
        }

        return Response(response_data, status=status.HTTP_200_OK)
