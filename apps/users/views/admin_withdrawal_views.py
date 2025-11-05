from __future__ import annotations

from datetime import datetime

from django.db.models import Case, CharField, Q, Value, When
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.enums import Role
from apps.users.models.withdrawal import Withdrawal
from apps.users.serializers.admin_withdrawal_serializers import (
    WithdrawalListItemSerializer,
)


@extend_schema(
    tags=["Admin"],
    operation_id="api_v1_admin_users_withdrawals_list",
    summary="관리자 탈퇴 회원 목록 조회",
    responses=WithdrawalListItemSerializer(many=True),
    parameters=[
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location="query",
            description="페이지네이션을 적용하여 가져올 페이지의 숫자",
        ),
        OpenApiParameter(
            name="page_size",
            type=OpenApiTypes.INT,
            location="query",
            description="페이지네이션을 적용하여 가져올 페이지의 사이즈, 최대 100",
        ),
        OpenApiParameter(name="keyword", type=OpenApiTypes.STR, location="query", description="검색에 사용할 키워드"),
        OpenApiParameter(
            name="role",
            enum=[r[0] for r in Role.choices],
            location="query",
            description="필터링에 사용할 역할 - user, staff, admin 만 허용",
        ),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location="query",
            description="정렬에 사용할 필드 - 'id', '-id', 'created_at', '-created_at', 'name', '-name' 만 허용",
        ),
    ],
)
class AdminWithdrawalListView(APIView):
    permission_classes = [IsAdminUser]
    ORDERING_PARAM = "ordering"
    ROLE_FILTERING_PARAM = "role"
    VALID_ROLE_PARAMS = [r[0] for r in Role.choices]
    VALID_ORDERING_PARAMS = ["id", "-id", "created_at", "-created_at", "name", "-name"]

    def _get_paginator(self, page_size: int = 20) -> PageNumberPagination:
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        paginator.page_query_param = "page"
        paginator.page_size_query_param = "page_size"

        return paginator

    def get(self, request: Request) -> Response:
        keyword = request.query_params.get("keyword")
        ordering = request.query_params.get(self.ORDERING_PARAM)
        role = request.query_params.get(self.ROLE_FILTERING_PARAM)

        qs = Withdrawal.objects.select_related("user").order_by(
            ordering if ordering and ordering in self.VALID_ORDERING_PARAMS else "id"
        )
        # annotate + case 구문을 통해 유저의 role을 필드로 가져옴
        qs = qs.annotate(
            role=Case(
                When(user__is_superuser=True, then=Value(Role.ADMIN)),
                When(user__is_staff=True, then=Value(Role.STAFF)),
                default=Value(Role.USER),
                output_field=CharField(),
            )
        )

        if role and role in self.VALID_ROLE_PARAMS:
            qs = qs.filter(role=role)

        # 키워드 검색 (OR 조건)
        if keyword:
            qs = qs.filter(
                Q(user__name__icontains=keyword)
                | Q(user__email__icontains=keyword)
                | Q(reason__icontains=keyword)
                | Q(reason_detail__icontains=keyword)
            )

        # 페이지네이션
        paginator = self._get_paginator()
        paginated_qs = paginator.paginate_queryset(qs, request)
        serializer = WithdrawalListItemSerializer(paginated_qs, many=True)
        response = paginator.get_paginated_response(serializer.data)
        response.data = {
            "detail": "회원 탈퇴 내역 목록 조회에 성공하였습니다.",
            "data": response.data,
        }

        return response
