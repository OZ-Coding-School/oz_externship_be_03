from __future__ import annotations

from django.db import transaction
from django.db.models import Case, CharField, Q, Value, When
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.views import ExceptionHandledAPIView
from apps.users.enums import Reason, Role
from apps.users.models.user import User
from apps.users.models.withdrawal import Withdrawal
from apps.users.permissions import IsAdminRole, IsStaffRole
from apps.users.serializers.admin_withdrawal_serializers import (
    WithdrawalDetailResponseSerializer,
    WithdrawalListItemSerializer,
)
from apps.users.services.admin_withdrawal_services import AdminWithdrawalService


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
        OpenApiParameter(
            name="reason",
            enum=Reason.values,
            location="query",
            description="탈퇴 사유 별 필터링에 사용되는 쿼리 파라미터 입니다.",
        ),
    ],
)
class AdminWithdrawalListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]
    ORDERING_PARAM = "ordering"
    ROLE_FILTERING_PARAM = "role"
    REASON_FILTERING_PARAM = "reason"
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
        reason = request.query_params.get(self.REASON_FILTERING_PARAM)

        qs = Withdrawal.objects.select_related("user").filter(user__isnull=False)

        if ordering:
            if ordering == "-name":
                qs = qs.order_by("-user__name", "-id")
            elif ordering == "name":
                qs = qs.order_by("user__name", "-id")
            else:
                qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-id")

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
            qs = qs.filter(role=role.lower())

        if reason and reason in Reason.values:
            qs = qs.filter(reason=reason.upper())

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
        operation_id="v1_admin_restore_withdrawn_user",
        summary="관리자 탈퇴 회원 복구",
        description=("관리자/스태프가 탈퇴 처리된 회원 계정을 복구\n"),
        parameters=[
            OpenApiParameter(
                name="withdrawal_id",
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
    def post(self, request: Request, withdrawal_id: int) -> Response:
        # 아래 작업을 하나의 단위로 수행(성공 시 커밋, 실패 시 롤백)
        with transaction.atomic():
            # select_for_update: 트랜잭션 종료까지 다른 트랜잭션의 UPDATE/DELETE 대기
            try:
                anchor: Withdrawal = Withdrawal.objects.select_related("user").get(id=withdrawal_id)
            except Withdrawal.DoesNotExist:
                raise NotFound("탈퇴 내역을 찾을 수 없습니다.")

            if anchor.user_id is None or anchor.user is None:
                raise NotFound("대상 사용자를 찾을 수 없습니다.")

            user: User = anchor.user

            if user.is_active:
                return Response({"error": "이미 활성화된 계정입니다."}, status=status.HTTP_409_CONFLICT)

            user.is_active = True
            user.updated_at = timezone.now()
            user.save(update_fields=["is_active", "updated_at"])

            Withdrawal.objects.filter(user_id=user.id).delete()

        return Response({"detail": "회원 복구에 성공하였습니다."}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Admin"],
    operation_id="api_v1_admin_withdrawals_detail",
    summary="관리자 탈퇴 회원 상세 조회",
    responses=WithdrawalDetailResponseSerializer,
)
class AdminWithdrawalDetailView(ExceptionHandledAPIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request: Request, withdrawal_id: int) -> Response:
        data = AdminWithdrawalService.get_withdrawal_detail(withdrawal_id)
        serializer = WithdrawalDetailResponseSerializer(data)
        return Response(
            {"detail": "탈퇴 내역 상세 조회에 성공하였습니다.", "data": serializer.data}, status=status.HTTP_200_OK
        )
