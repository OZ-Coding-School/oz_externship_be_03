import uuid
from datetime import timedelta
from typing import Any

from django.shortcuts import get_object_or_404
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
        recruitment = serializer.save()  # DB 저장
        return Response(self.serializer_class(recruitment).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="recruitments_list",
        tags=["Recruitments"],
        summary="스터디 구인공고 목록 조회 API",
        responses={200: RecruitmentSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        recruitments = Recruitment.objects.all().order_by("-created_at")
        serializer = self.serializer_class(recruitments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RecruitmentRetrieveUpdateDestroyAPIView(APIView):
    serializer_class = RecruitmentDetailSerializer
    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    def get_object(self, recruitment_id: int) -> Recruitment:
        return get_object_or_404(Recruitment, id=recruitment_id)

    @extend_schema(tags=["Recruitments"], summary="스터디 구인공고 상세 조회 API")
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_id)
        serializer = self.serializer_class(recruitment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(tags=["Recruitments"], summary="스터디 구인공고 수정 API")
    def put(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_id)
        serializer = self.serializer_class(recruitment, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()  # DB 업데이트
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(tags=["Recruitments"], summary="스터디 구인공고 삭제 API")
    def delete(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_id)
        recruitment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
