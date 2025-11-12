import math
from typing import Any, List, cast

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.groups import StudyGroup, StudyGroupStatus
from ..paginations import StudyGroupPagination
from ..permissions import IsGroupLeader
from ..serializers.groups import (
    AdminStudyGroupDetailSerializer,
    AdminStudyGroupListSerializer,
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
        serializer = StudyGroupCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="v1_studies_groups_list",
        tags=["StudyGroup"],
        summary="스터디 그룹 전체 목록 조회 API",
        parameters=[
            OpenApiParameter(name="page", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="그룹 상태 필터링: 'PENDING' = 대기중, 'ONGOING' = 진행중, 'ENDED' = 완료됨",
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="검색어로 필터링",
            ),
        ],
        responses={
            200: StudyGroupListSerializer(many=True),
        },
    )
    def get(self, request: Request) -> Response:

        queryset = StudyGroup.objects.order_by("-created_at")
        total_groups = queryset.count()
        total_pages = math.ceil(total_groups / StudyGroupPagination.page_size)

        status_param = request.query_params.get("status")
        if status_param in StudyGroupStatus.values:
            queryset = queryset.filter(status=status_param)

        search_param = request.query_params.get("search", "")
        if search_param:
            queryset = queryset.filter(name__icontains=search_param)

        queryset = queryset.annotate(current_headcount=Count("members"))

        queryset = queryset.prefetch_related("members", "lectures")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, self.request)
        serializer = StudyGroupListSerializer(
            page, many=True, context={"request": request, "total_pages": total_pages, "total_groups": total_groups}
        )
        return paginator.get_paginated_response(serializer.data)


class StudyGroupDetailUpdateView(APIView):
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    def get_permissions(self) -> List[BasePermission]:
        if self.request.method == "GET":
            return [IsAuthenticated()]
        if self.request.method == "PUT":
            return [IsAuthenticated(), IsGroupLeader()]
        return cast(List[BasePermission], super().get_permissions())

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
        obj = get_object_or_404(StudyGroup.objects.prefetch_related("group_members", "lectures"), uuid=obj_uuid)
        self.check_object_permissions(request, obj)

        serializer = StudyGroupDetailSerializer(obj, context={"request": request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="v1_studies_groups_update",
        tags=["StudyGroup"],
        summary="스터디 그룹 정보 수정 API",
        description=("UUID 값을 입력해주세요."),
        request=StudyGroupCreateSerializer,
        responses={
            200: StudyGroupCreateSerializer,
        },
    )
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        obj_uuid = self.kwargs.get("group_uuid")
        obj = get_object_or_404(StudyGroup.objects.prefetch_related("lectures"), uuid=obj_uuid)

        self.check_object_permissions(request, obj)

        serializer = StudyGroupCreateSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response = StudyGroupDetailSerializer(obj, context={"request": request})
        return Response(response.data, status=status.HTTP_200_OK)


# 어드민 스터디그룹 목록 조회
class AdminStudyGroupListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StudyGroupPagination

    @extend_schema(
        operation_id="v1_admin_studies_groups_list",
        tags=["Admin"],
        summary="어드민용 스터디 그룹 목록 조회",
        description=(
            "관리자 전용. "
            "검색(그룹명), 필터(종료 여부), 정렬(최신/오래된/이름순), "
            "페이지네이션(limit-offset) 기능 제공."
        ),
        responses={200: AdminStudyGroupListSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        # 관리자 접근 제약
        if not request.user.is_superuser:
            return Response({"detail": "관리자만 접근 가능합니다."}, status=status.HTTP_403_FORBIDDEN)

        queryset = StudyGroup.objects.annotate(current_headcount=Count("members"))

        # 검색
        search_param = request.query_params.get("search")
        if search_param:
            queryset = queryset.filter(name__icontains=search_param)

        # 필터 (상태)
        status_param = request.query_params.get("status")
        if status_param in StudyGroupStatus.values:
            queryset = queryset.filter(status=status_param)

        # 정렬
        ordering = request.query_params.get("ordering", "latest")
        ordering_map = {
            "latest": "-created_at",
            "oldest": "created_at",
            "name_asc": "name",
            "name_desc": "-name",
        }
        queryset = queryset.order_by(ordering_map.get(ordering, "-created_at"))

        # 페이지네이션
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        serializer = AdminStudyGroupListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


# 어드민 스터디그룹 상세 조회
class AdminStudyGroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="v1_admin_studies_groups_detail",
        tags=["Admin"],
        summary="관리자 스터디 그룹 상세 조회",
        description="관리자 전용. 리더는 멤버 목록 최상단에 정렬되어 표시됩니다.",
        responses={200: AdminStudyGroupDetailSerializer},
    )
    def get(self, request: Request, group_uuid: str) -> Response:
        if not request.user.is_superuser:
            return Response({"detail": "관리자만 접근 가능합니다."}, status=status.HTTP_403_FORBIDDEN)

        group = get_object_or_404(
            StudyGroup.objects.prefetch_related(
                "group_members__user",
                "lectures",
            ),
            uuid=group_uuid,
        )

        serializer = AdminStudyGroupDetailSerializer(group, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
