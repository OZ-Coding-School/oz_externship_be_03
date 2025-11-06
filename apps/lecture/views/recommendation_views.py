from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.serializers.lecture_serializers import LectureListSerializer
from apps.lecture.services.recommendation_service.recommender import (
    RecommendationService,
)


class RecommendationView(APIView):
    """맞춤 추천 강의 API"""

    serializer_class = LectureListSerializer
    permission_classes = [IsAuthenticated]

    RECOMMENDATION_COUNT = 3

    def get_recommendation_service(self) -> RecommendationService:
        """RecommendationService 인스턴스를 싱글턴 패턴으로 반환"""
        if not hasattr(self, "_recommendation_service"):
            self._recommendation_service = RecommendationService()
        return self._recommendation_service

    @extend_schema(
        tags=["Lectures"],
        summary="사용자 맞춤 추천 강의 조회 API",
        description="사용자 맞춤 추천 강의 3개",
        responses={
            200: LectureListSerializer(many=True),
            401: {"description": "인증이 필요합니다."},
        },
    )
    def get(self, request: Request) -> Response:
        """사용자 맞춤 추천 강의 조회"""
        user_id: int = cast(int, request.user.id)

        recommendation_service = self.get_recommendation_service()
        lectures_queryset = recommendation_service.recommend_lectures(user_id, self.RECOMMENDATION_COUNT)

        serializer = self.serializer_class(
            lectures_queryset,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "detail": "맞춤 강의 추천 조회가 완료되었습니다.",
                "data": {"recommendations": serializer.data},
            },
            status=status.HTTP_200_OK,
        )
