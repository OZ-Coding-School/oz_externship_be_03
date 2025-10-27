import uuid
from datetime import timedelta
from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.recruitments import Recruitment
from apps.recruitments.serializers.recruitments import (
    RecruitmentDetailSerializer,
    RecruitmentSerializer,
)


class RecruitmentListCreateAPIView(APIView):
    serializer_class = RecruitmentSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(
        tags=["Recruitments"],
        summary="스터디 구인공고 등록 API",
        request=RecruitmentSerializer,
        responses={201: RecruitmentSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="recruitments_list",
        tags=["Recruitments"],
        summary="스터디 구인공고 목록 조회 API",
        responses={200: RecruitmentSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        mock_data = [
            Recruitment(
                id=i,
                uuid=uuid.uuid4(),
                title=f"스터디 구인공고 {i}",
                content=f"이것은 스터디 구인공고 {i}의 내용입니다.",
                estimated_fee=5000 * i,
                expected_headcount=i % 10 + 1,
                views_count=i * 13,
                close_at=timezone.now() + timedelta(days=14),
                is_closed=False,
                created_at=timezone.now() - timedelta(days=i),
                updated_at=timezone.now(),
            )
            for i in range(1, 6)
        ]
        serializer = self.serializer_class(mock_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RecruitmentRetrieveUpdateDestroyAPIView(APIView):
    serializer_class = RecruitmentDetailSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(tags=["Recruitments"], summary="스터디 구인공고 상세 조회 API")
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        mock_data = Recruitment(
            id=recruitment_id,
            uuid=uuid.uuid4(),
            title="Mock 스터디 구인공고",
            content="이것은 Mock 스터디 구인공고의 내용입니다.",
            estimated_fee=15000,
            expected_headcount=5,
            views_count=200,
            close_at=timezone.now() + timedelta(days=14),
            is_closed=False,
            created_at=timezone.now() - timedelta(days=3),
            updated_at=timezone.now(),
        )
        serializer = self.serializer_class(mock_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(tags=["Recruitments"], summary="스터디 구인공고 수정 API")
    def put(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        mock_data = Recruitment(
            id=recruitment_id,
            uuid=uuid.uuid4(),
            title=serializer.validated_data.get("title", "Mock 스터디 구인공고"),
            content=serializer.validated_data.get("content", "Mock 내용"),
            estimated_fee=serializer.validated_data.get("estimated_fee", 15000),
            expected_headcount=serializer.validated_data.get("expected_headcount", 5),
            views_count=serializer.validated_data.get("views_count", 200),
            close_at=timezone.now() + timedelta(days=10),
            is_closed=serializer.validated_data.get("is_closed", False),
            created_at=timezone.now() - timedelta(days=1),
            updated_at=timezone.now(),
        )

        return Response(self.serializer_class(mock_data).data, status=status.HTTP_200_OK)

    @extend_schema(tags=["Recruitments"], summary="스터디 구인공고 삭제 API")
    def delete(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)
