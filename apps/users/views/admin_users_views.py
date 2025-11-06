from __future__ import annotations

from typing import Any, Dict

from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.paginators import StandardPageNumberPagination
from apps.core.views import ExceptionHandledAPIView
from apps.users.enums import Role, UserStatus
from apps.users.permissions import IsAdminRole, IsStaffRole
from apps.users.serializers.admin_users_serializer import (
    AdminUserDetailSerializer,
    AdminUserItemSerializer,
    AdminUserListResponseSerializer,
    AdminUserRoleUpdateRequestSerializer,
    AdminUserUpdateResponseSerializer,
    AdminUserUpdateSerializer,
)
from apps.users.services.admin_users_services import AdminUserService


# 관리자: 회원 목록 조회
class AdminUserListView(ExceptionHandledAPIView):
    permission_classes = [IsAuthenticated, IsStaffRole]
    pagination_class = StandardPageNumberPagination

    @extend_schema(
        tags=["Admin"],
        summary="관리자 - 회원 목록 조회",
        parameters=[
            OpenApiParameter(name="page", required=False, type=int, description="페이지 번호(기본 1)"),
            OpenApiParameter(name="limit", required=False, type=int, description="페이지당 개수(기본 20)"),
            OpenApiParameter(name="q", required=False, type=str, description="검색어(이메일/닉네임/이름/ID)"),
            OpenApiParameter(
                name="role",
                required=False,
                type=OpenApiTypes.STR,
                enum=[r.value for r in Role],
                description="권한 필터(admin|staff|user)",
            ),
            OpenApiParameter(
                name="status",
                required=False,
                type=OpenApiTypes.STR,
                enum=[s.value for s in UserStatus],
                description="상태 필터(active|inactive|withdrawal_pending)",
            ),
            OpenApiParameter(
                name="order", required=False, type=str, description="정렬 필드(기본 'id' 오름차순, '-id' 내림차순)"
            ),
        ],
        responses={200: AdminUserListResponseSerializer},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        qp = request.query_params
        q = qp.get("q")
        role = qp.get("role")
        stat = qp.get("status")
        order = qp.get("order", "id")

        base_qs = AdminUserService.get_user_list(order=order, q=q, role=role, status=stat)

        paginator = self.pagination_class()
        page_qs = paginator.paginate_queryset(base_qs, request, view=self) or base_qs

        items = AdminUserItemSerializer(instance=list(page_qs), many=True).data
        meta = paginator.meta(request)

        return Response(
            {
                "detail": "회원 목록 조회에 성공하였습니다.",
                "data": {
                    "users": items,
                    "pagination": meta,
                },
            },
            status=status.HTTP_200_OK,
        )


# 관리자 - 회원 상세 조회, 회원 정보 수정, 회원 정보 삭제
class AdminUserView(ExceptionHandledAPIView):
    """
    관리자 - 회원 상세 조회 / 수정 / 삭제
    - GET/PATCH: 스태프 이상 접근 허용
    - DELETE   : 관리자(superuser)만 허용
    """

    permission_classes = [IsAuthenticated]

    # 메서드별 퍼미션 분기 (DELETE만 관리자 권한 필요)
    def get_permissions(self) -> list[BasePermission]:
        base: list[BasePermission] = [IsAuthenticated()]
        if self.request.method == "DELETE":
            return base + [IsAdminRole()]
        if self.request.method in ("GET", "PATCH"):
            return base + [IsStaffRole()]
        return base

    @extend_schema(
        tags=["Admin"],
        summary="관리자 - 회원 상세 조회",
        responses={200: AdminUserDetailSerializer, 404: OpenApiTypes.OBJECT},
        operation_id="v1_admin_users_retrieve_detail",
    )
    def get(self, request: Request, user_id: int) -> Response:
        # 회원 상세 조회
        try:
            user = AdminUserService.get_user(user_id)
        except Http404:
            return Response({"error": "회원 정보를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminUserDetailSerializer(user)
        return Response(
            {
                "detail": "회원 상세 정보를 조회했습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Admin"],
        summary="관리자 - 회원 정보 수정",
        request=AdminUserUpdateSerializer,
        responses={200: AdminUserUpdateResponseSerializer, 404: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, user_id: int) -> Response:
        # 회원 정보 수정
        try:
            user = AdminUserService.get_user(user_id)
        except Http404:
            return Response({"error": "회원 정보를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        ser = AdminUserUpdateSerializer(instance=user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        validated: Dict[str, Any] = dict(ser.validated_data)

        updated_user = AdminUserService.update_user_info(user, validated)
        response_data = AdminUserUpdateResponseSerializer(updated_user).data

        return Response(
            {
                "detail": "회원 정보가 수정되었습니다.",
                "data": response_data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Admin"], summary="관리자 - 회원 삭제", responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT}
    )
    def delete(self, request: Request, user_id: int) -> Response:
        try:
            user = AdminUserService.get_user(user_id)
        except Http404:
            return Response(
                {"error": "회원 정보를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        AdminUserService.delete_user(user)
        return Response(
            {"detail": "회원이 삭제되었습니다."},
            status=status.HTTP_200_OK,
        )


# 관리자: 회원 권한(role) 변경
@extend_schema(
    tags=["Admin"],
    summary="관리자 - 회원 권한 변경",
    request=AdminUserRoleUpdateRequestSerializer,
    responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    operation_id="v1_admin_users_update_role",
)
class AdminUserRoleUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def patch(self, request: Request, user_id: int, *args: Any, **kwargs: Any) -> Response:
        serializer = AdminUserRoleUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data["role"]

        try:
            user = AdminUserService.get_user(user_id)
        except Http404:
            return Response(
                {"error": "회원 정보를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        AdminUserService.change_user_role(user, role)

        return Response(
            {
                "detail": "회원 권한이 변경되었습니다.",
            },
            status=status.HTTP_200_OK,
        )
