from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
from apps.studies.serializers.reviews import ReviewCreateSerializer


class ReviewCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="CreateReview",
        request=ReviewCreateSerializer,
        responses={
            201: OpenApiResponse(description="리뷰가 생성되었습니다."),
            401: OpenApiResponse(description="인증 필요"),
            403: OpenApiResponse(description="권한 없음"),
            404: OpenApiResponse(description="대상 리소스 없음(예: study_group)"),
            409: OpenApiResponse(description="중복 리뷰 또는 무결성 충돌"),
            422: OpenApiResponse(description="검증 실패(필드/비즈니스 룰"),
        },
        tags=["StudyGroupReview"],
        summary="리뷰 작성",
        description="경로의 group_id를 사용해 해당 스터디 그룹에 리뷰를 생성합니다.",
        examples=[
            OpenApiExample(
                "create Review (no study_group in body)",
                value={"star_rating": 5, "content": "좋았어요!"},
                request_only=True,
            )
        ],
    )
    def post(self, request: Request, group_id: UUID, *args: Any, **kwargs: Any) -> Response:
        study_group = get_object_or_404(StudyGroup, pk=group_id)

        data = {**request.data, "study_group": str(study_group.id)}
        serializer = ReviewCreateSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=422)

        try:
            serializer.save()
        except IntegrityError:
            return Response({"detail": "이미 해당 스터디에 리뷰를 작성했습니다"}, status=409)

        return Response(serializer.data, status=201)
