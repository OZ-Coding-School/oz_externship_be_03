from typing import Any

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.groups import StudyGroup
from ..paginations import StudyGroupPagination
from ..serializers.groups import (
    StudyGroupCreateSerializer,
    StudyGroupDetailSerializer,
    StudyGroupListSerializer,
)


class StudyGroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StudyGroupPagination

    # JSON, 이미지 파일을 요청으로부터 넘겨받기 위함
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(
        operation_id="v1_studies_groups_create",
        tags=["StudyGroup"],
        summary="스터디 그룹 생성 API",
        request=StudyGroupCreateSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = StudyGroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="v1_studies_groups_list",
        tags=["StudyGroup"],
        summary="스터디 그룹 전체 목록 조회 API",
        responses={
            200: StudyGroupListSerializer(many=True),
        },
    )
    def get(self, request: Request) -> Response:

        queryset = StudyGroup.objects.order_by("-created_at")

        status_param = request.query_params.get("status")
        if status_param == "ENDED":
            queryset = queryset.filter(status=status_param)

        queryset = queryset.annotate(current_headcount=Count("members"))

        queryset = queryset.prefetch_related("members", "lectures__lecture")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, self.request)
        serializer = StudyGroupListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class StudyGroupDetailUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(
        operation_id="v1_studies_groups_detail",
        tags=["StudyGroup"],
        summary="스터디 그룹 상세 조회 API",
        description=("UUID 값을 입력해주세요."),
        responses={
            200: StudyGroupDetailSerializer,
        },
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        obj_uuid = self.kwargs.get("group_uuid")
        obj = get_object_or_404(StudyGroup.objects.prefetch_related("members", "lectures__lecture"), uuid=obj_uuid)

        serializer = StudyGroupDetailSerializer(obj, context={"request": request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="v1_studies_groups_update",
        tags=["StudyGroup"],
        summary="스터디 그룹 정보 수정 API",
        description=("UUID 값을 입력해주세요."),
        responses={
            200: StudyGroupCreateSerializer,
        },
    )
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        obj_uuid = self.kwargs.get("group_uuid")
        obj = get_object_or_404(StudyGroup.objects.prefetch_related("lectures__lecture"), uuid=obj_uuid)

        serializer = StudyGroupCreateSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response = StudyGroupDetailSerializer(obj, context={"request": request})
        return Response(response.data, status=status.HTTP_200_OK)
