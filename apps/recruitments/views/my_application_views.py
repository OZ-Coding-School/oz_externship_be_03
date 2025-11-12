from __future__ import annotations

from typing import cast

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.application import Application
from apps.recruitments.models.recruitment_images import RecruitmentImage
from apps.recruitments.serializers.my_application_serializers import (
    MyApplicationDetailSerializer,
    MyApplicationSerializer,
)
from apps.users.models import User


class MyApplicationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Applications"],
        summary="내가 지원한 공고 내역 조회",
        description="로그인한 사용자가 자신이 지원한 공고 내역을 조회합니다.",
        responses=inline_serializer(
            name="MyApplicationsAPIResponse",
            fields={
                "detail": serializers.CharField(),
                "data": MyApplicationSerializer(),
            },
        ),
    )
    def get(self, request: Request) -> Response:
        queryset = (
            Application.objects.filter(user=cast(User, request.user))
            .select_related("recruitment")
            .prefetch_related(
                Prefetch(
                    "recruitment__images",
                    queryset=RecruitmentImage.objects.order_by("id"),
                )
            )
            .order_by("-created_at")
        )
        data = MyApplicationSerializer(queryset, many=True).data
        return Response(
            {"detail": "내 지원 목록 조회에 성공했습니다.", "data": data},
            status=status.HTTP_200_OK,
        )


class MyApplicationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Applications"],
        summary="내가 지원한 공고 상세 조회",
        description="내 지원 내역 중 특정 지원서 상세를 조회합니다.",
        responses=inline_serializer(
            name="MyApplicationDetailResponse",
            fields={
                "detail": serializers.CharField(),
                "data": MyApplicationDetailSerializer(),
            },
        ),
    )
    def get(self, request: Request, application_uuid: str) -> Response:
        app = get_object_or_404(
            Application.objects.select_related("recruitment").prefetch_related("recruitment__images"),
            user=cast(User, request.user),
            uuid=application_uuid,
        )
        data = MyApplicationDetailSerializer(app).data
        return Response({"detail": "지원서 조회에 성공했습니다.", "data": data}, status=status.HTTP_200_OK)
