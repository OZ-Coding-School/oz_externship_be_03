from __future__ import annotations

from typing import Any, List

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.recruitments.models import Recruitment, Tag
from apps.recruitments.serializers.tag import (
    RecruitmentTagAddSerializer,
    TagSerializer,
)
from apps.recruitments.services.tags import add_tags_to_recruitment, search_tags


@extend_schema(
    tags=["recruitments"],
    summary="스터디 구인 공고 태그 검색 및 신규 등록",
    description=(
        "공고 작성 시 사용자는 태그를 검색하여 기존 태그를 선택하거나 "
        "존재하지 않는 경우 새로 등록할 수 있습니다.\n\n"
        "- 부분 일치 / 완전 일치 검색 지원\n"
        "- 페이지당 5개 항목 표시 (pagination)\n"
        "- 중복 태그 등록 시 409 Conflict 반환"
    ),
    parameters=[
        OpenApiParameter(
            name="keyword",
            description="검색 키워드 (태그명 일부 혹은 완전 일치)",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="page",
            description="페이지 번호 (기본값: 1)",
            required=False,
            type=int,
        ),
    ],
    request=RecruitmentTagAddSerializer,
    responses={
        200: OpenApiResponse(response=TagSerializer, description="태그 검색 성공"),
        201: OpenApiResponse(response=RecruitmentTagAddSerializer, description="태그 등록 성공"),
        400: OpenApiResponse(description="요청 데이터 형식 오류"),
        401: OpenApiResponse(description="인증되지 않은 사용자"),
        409: OpenApiResponse(description="이미 존재하는 태그명으로 등록 시도"),
    },
)
class RecruitmentTagSearchCreateAPIView(generics.GenericAPIView[Any]):
    """REQ-RECM-002 — 스터디 구인 공고 작성 시 태그 검색 및 추가"""

    permission_classes = [IsAuthenticated]
    serializer_class = RecruitmentTagAddSerializer

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        keyword: str = request.query_params.get("keyword", "")
        qs = search_tags(keyword)
        page = self.paginate_queryset(qs)
        serializer = TagSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = RecruitmentTagAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        created_names: List[str] = []
        duplicate_names: List[str] = []

        for name in serializer.validated_data["tags"]:
            tag_name = name.strip()
            tag, created = Tag.objects.get_or_create(name=tag_name)
            if created:
                created_names.append(tag.name)
            else:
                duplicate_names.append(tag.name)

        if duplicate_names:
            return Response(
                {"error": f"이미 존재하는 태그입니다: {', '.join(duplicate_names)}"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"created_tags": created_names, "message": "태그가 정상적으로 등록되었습니다."},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["recruitments"],
    summary="특정 공고에 태그 검색 및 추가",
    description=(
        "공고 수정 시 해당 공고에 추가할 태그를 검색하거나 신규 등록할 수 있습니다.\n\n"
        "- 공고당 최대 5개 태그까지 추가 가능\n"
        "- 이미 등록된 태그를 다시 추가하려는 경우 400 Bad Request 반환"
    ),
    parameters=[
        OpenApiParameter(name="keyword", description="검색 키워드", required=False, type=str),
        OpenApiParameter(name="page", description="페이지 번호 (기본값: 1)", required=False, type=int),
    ],
    request=RecruitmentTagAddSerializer,
    responses={
        200: OpenApiResponse(response=TagSerializer, description="태그 검색 성공"),
        201: OpenApiResponse(description="공고에 태그 추가 성공"),
        400: OpenApiResponse(description="태그 수 초과 또는 형식 오류"),
        401: OpenApiResponse(description="인증되지 않은 사용자"),
        404: OpenApiResponse(description="공고를 찾을 수 없음"),
    },
)
class RecruitmentTagSearchAddForRecruitmentAPIView(generics.GenericAPIView[Any]):
    """REQ-RECM-008 — 스터디 구인 공고 수정 시 태그 검색 및 추가"""

    permission_classes = [IsAuthenticated]
    serializer_class = RecruitmentTagAddSerializer

    def get_object(self) -> Recruitment:
        """recruitment_id로 해당 공고를 조회"""
        return Recruitment.objects.get(pk=self.kwargs["recruitment_id"])

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        keyword: str = request.query_params.get("keyword", "")
        qs = search_tags(keyword)
        page = self.paginate_queryset(qs)
        serializer = TagSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object()
        serializer = RecruitmentTagAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            added: List[str] = add_tags_to_recruitment(recruitment, serializer.validated_data["tags"])
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"recruitment_id": recruitment.id, "added_tags": added, "message": "태그가 정상적으로 추가되었습니다."},
            status=status.HTTP_201_CREATED,
        )
