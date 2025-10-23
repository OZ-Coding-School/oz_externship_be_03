from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.serializers.lecture_serializers import LectureListSerializer
from apps.lecture.services.recommendation_service import RecommendationService


class RecommendationView(APIView):
    """맞춤 추천 강의 API"""

    serializer_class = LectureListSerializer
    permission_classes = [IsAuthenticated]

    recommendation_service: RecommendationService = RecommendationService()
    RECOMMENDATION_COUNT = 3

    @extend_schema(
        operation_id="v1_lectures_recommendations",
        tags=["Lectures"],
        summary="사용자 맞춤 추천 강의 조회 API",
        responses={
            200: LectureListSerializer(many=True),
            401: {"description": "Unauthorized: 인증 토큰 누락 또는 만료"},
        },
    )
    def get(self, request: Request) -> Response:
        user_id = request.user.id
        # user_id의 타입이 Optional[int] 이므로 mypy는 None 가능성 경고 발생
        # 실제로 IsAuthenticated이므로 None일 가능성은 거의 없으나
        # mypy 정적 타입 검사 무시를 위해 None 체크 코드 추가
        if user_id is None:
            # None인 경우 예외 또는 에러 응답 처리
            # 실제로는 인증 실패 시 여기 오지 않지만 안정성 및 타입 검사 통과용
            return Response({"detail": "User ID is missing."}, status=status.HTTP_401_UNAUTHORIZED)
        # 이후 코드에서 user_id가 int 타입임을 mypy에 명확히 알림
        # 런타임 시에도 user_id가 실제 int인지 보증하는 검증 역할 겸함
        assert isinstance(user_id, int)

        # 1. RecommendationService를 통해 추천 강의 QuerySet 3개 조회
        lectures_queryset = self.recommendation_service.recommend_lectures_for_user(user_id, self.RECOMMENDATION_COUNT)

        # 2. 강의 목록 데이터 직렬화
        serializer = self.serializer_class(lectures_queryset, many=True, context={"request": request})

        return Response(
            {
                "detail": "맞춤 강의 추천 조회가 완료되었습니다.",
                "data": {
                    "recommendations": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )
