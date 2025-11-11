from uuid import UUID

from django.db.models import Q, QuerySet, TextChoices
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models import Application, ApplicationStatus
from apps.recruitments.serializers.admin_application_serializers import (
    AdminApplicationDetailSerializer,
    AdminApplicationSerializer,
)
from apps.users.permissions import IsStaffRole


class OrderingEnum(TextChoices):
    LATEST = "-created_at", "latest"
    OLDEST = "created_at", "oldest"


class ApplicationAdminAPIView(APIView):
    serializer_class = AdminApplicationSerializer
    permission_classes = [IsStaffRole]
    pagination_class = LimitOffsetPagination

    @extend_schema(
        tags=["Application"],
        summary="어드민용 모든 지원 내역 목록 조회 API",
        operation_id="v1_admin_application_list",
        parameters=[
            OpenApiParameter(
                name="keyword",
                required=False,
                type=OpenApiTypes.STR,
                description="지원 내역 검색을 위한 쿼리 파라미터입니다. 해당 키워드가 공고 제목, 지원자의 이름, 지원자의 이메일 중 일치하는 부분이 있으면 결과값으로 반환합니다.",
            ),
            OpenApiParameter(
                name="status",
                required=False,
                enum=[v.lower() for v in ApplicationStatus.values],
                description="상태별 필터링을 위한 쿼리파라미터입니다.",
            ),
            OpenApiParameter(
                name="ordering",
                required=False,
                enum=OrderingEnum.labels,
                description="정렬을 위한 쿼리파라미터 입니다. 기본값은 latest.",
            ),
        ],
    )
    def get(self, request: Request) -> Response:
        paginator = self.get_paginator()
        base_queryset = self.get_queryset(request=request)
        paginated_queryset = paginator.paginate_queryset(base_queryset, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def get_paginator(self) -> LimitOffsetPagination:
        paginator = self.pagination_class()
        paginator.default_limit = 10
        paginator.max_limit = 100

        return paginator

    def get_queryset(self, request: Request) -> QuerySet[Application]:
        queryset = Application.objects.select_related("user", "recruitment")
        keyword = request.query_params.get("keyword", "")
        status = request.query_params.get("status", "")
        ordering = request.query_params.get("ordering", "")
        # 검색 키워드가 있으면 해당 키워드가 공고 제목, 지원자 이름, 지원자 이메일에 하나라도 포함되어 있다면 결과에 포함
        if keyword:
            queryset = queryset.filter(
                Q(recruitment__title__icontains=keyword)
                | Q(user__name__icontains=keyword)
                | Q(user__email__icontains=keyword)
            )

        if status.upper() in ApplicationStatus.values:
            queryset = queryset.filter(status=status)

        if ordering_value := getattr(OrderingEnum, ordering.upper(), OrderingEnum.LATEST):
            queryset = queryset.order_by(ordering_value)
        else:
            queryset = queryset.order_by("-created_at")

        return queryset


class ApplicationDetailAdminAPIView(APIView):
    serializer_class = AdminApplicationDetailSerializer
    permission_classes = [IsStaffRole]

    @extend_schema(
        tags=["Application"],
        summary="어드민용 지원 내역 상세 조회 API",
    )
    def get(self, request: Request, application_uuid: UUID) -> Response:
        application = self.get_object(application_uuid)
        serializer = self.serializer_class(application)
        return Response(serializer.data)

    def get_object(self, application_uuid: UUID) -> Application:
        try:
            return Application.objects.get(uuid=application_uuid)
        except Application.DoesNotExist:
            raise NotFound(f"application_uuid: {application_uuid} not found")
