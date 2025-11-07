from __future__ import annotations

from django.db import transaction
from django.db.models import Case, CharField, Q, Value, When
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.views import ExceptionHandledAPIView
from apps.users.enums import Role
from apps.users.models.user import User
from apps.users.models.withdrawal import Withdrawal
from apps.users.permissions import IsStaffRole
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


class AdminUserRestoreView(ExceptionHandledAPIView):
    """
    어드민 탈퇴 회원 복구
    """

    permission_classes = [IsAuthenticated, IsStaffRole]

    @extend_schema(
        tags=["Admin"],
        operation_id="v1_admin_users_restore_withdrawn_user",
        summary="관리자 탈퇴 회원 복구",
        description=("관리자/스태프가 탈퇴 처리된 회원 계정을 복구\n"),
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=int,
                location=OpenApiParameter.PATH,
                required=True,
                description="복구할 탈퇴 회원의 ID",
            ),
        ],
        responses={
            200: OpenApiResponse(description="복구 완료된 사용자 정보"),
            404: OpenApiResponse(description="대상 사용자를 찾을 수 없음"),
            409: OpenApiResponse(description="복구 불가 상태(이미 활성 사용자 등)"),
        },
    )
    def post(self, request: Request, user_id: int) -> Response:
        # 아래 작업을 하나의 단위로 수행(성공 시 커밋, 실패 시 롤백)
        with transaction.atomic():
            # select_for_update: 트랜잭션 종료까지 다른 트랜잭션의 UPDATE/DELETE 대기
            user = User.objects.select_for_update().filter(pk=user_id).first()
            if not user:
                return Response({"error": "대상 사용자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

            has_withdrawal = Withdrawal.objects.filter(user_id=user.id).exists()
            if not has_withdrawal:
                return Response({"error": "탈퇴 내역을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

            if user.is_active:
                return Response({"error": "이미 활성화된 계정입니다."}, status=status.HTTP_409_CONFLICT)

            user.is_active = True
            user.updated_at = timezone.now()
            user.save(update_fields=["is_active", "updated_at"])

            Withdrawal.objects.filter(user_id=user.id).delete()

        return Response({"detail": "회원 복구에 성공하였습니다."}, status=status.HTTP_200_OK)
