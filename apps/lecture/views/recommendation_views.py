from typing import Optional

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import LectureBookmark
from apps.lecture.serializers.lecture_serializers import LectureListSerializer
from apps.lecture.services.recommender import RecommendationService


class RecommendationView(APIView):
    """맞춤 추천 강의 API"""

    serializer_class = LectureListSerializer
    permission_classes = [IsAuthenticated]

    RECOMMENDATION_COUNT = 3

    def get_recommendation_service(self) -> RecommendationService:
        """
        RecommendationService 인스턴스를 싱글턴 패턴으로 로드하거나 캐시된 인스턴스를 반환.
        모델 로드/훈련 과정의 반복을 회피.
        """
        if not hasattr(self, "_recommendation_service"):
            self._recommendation_service = RecommendationService()
        return self._recommendation_service

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
        """
        로그인된 사용자의 ID를 기반으로 맞춤 강의 추천 목록을 반환.
        """
        user_id: Optional[int] = request.user.id
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

        user_bookmarked_ids = set(LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True))

        recommendation_service = self.get_recommendation_service()
        lectures_queryset = recommendation_service.recommend_lectures(user_id, self.RECOMMENDATION_COUNT)

        lectures_queryset = lectures_queryset.prefetch_related(
            "lecturecategory_set__category",
        ).select_related()

        serializer = self.serializer_class(
            lectures_queryset,
            many=True,
            context={
                "request": request,
                "bookmarked_ids": user_bookmarked_ids,
            },
        )
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
