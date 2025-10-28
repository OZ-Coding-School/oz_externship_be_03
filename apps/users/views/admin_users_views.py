from __future__ import annotations

from typing import Any

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.admin_users_serializer import (
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    AdminUserRoleUpdateRequestSerializer,
    AdminUserRoleUpdateResponseSerializer,
    AdminUserUpdateSerializer,
)
from apps.users.services.admin_users_services import AdminUserService


# 관리자: 회원 목록 조회
@extend_schema(
    tags=["Admin"],
    summary="관리자 - 회원 목록 조회",
    responses={200: AdminUserListSerializer(many=True)},
)
class AdminUserListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        users = AdminUserService.get_user_list()
        serializer = AdminUserListSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# 관리자: 회원 상세 조회
@extend_schema(
    tags=["Admin"],
    summary="관리자 - 회원 상세 조회",
    responses={200: AdminUserDetailSerializer},
)
class AdminUserDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request: Request, user_id: int, *args: Any, **kwargs: Any) -> Response:
        try:
            user = AdminUserService.get_user(user_id)
        except Http404:
            return Response(
                {"error": "회원 정보를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminUserDetailSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# 관리자: 회원 정보 수정
@extend_schema(
    tags=["Admin"],
    summary="관리자 - 회원 정보 수정",
    request=AdminUserUpdateSerializer,
    responses={200: AdminUserDetailSerializer},
)
class AdminUserUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request: Request, user_id: int, *args: Any, **kwargs: Any) -> Response:
        allowed_fields = set(AdminUserUpdateSerializer.Meta.fields)
        invalid_fields = set(request.data.keys()) - allowed_fields
        if invalid_fields:
            return Response(
                {"error": f"잘못된 필드가 포함되어 있습니다: {', '.join(invalid_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = AdminUserService.get_user(user_id)
        updated_user = AdminUserService.update_user_info(user, serializer.validated_data)

        response_data = AdminUserDetailSerializer(updated_user).data
        return Response(response_data, status=status.HTTP_200_OK)


# 관리자: 회원 삭제
@extend_schema(
    tags=["Admin"],
    summary="관리자 - 회원 삭제",
    responses={204: None},
)
class AdminUserDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request: Request, user_id: int) -> Response:
        if not request.user.is_superuser:
            raise PermissionDenied("슈퍼유저만 회원을 삭제할 수 있습니다.")

        try:
            user = AdminUserService.get_user(user_id)
        except Http404:
            return Response(
                {"error": "회원 정보를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        AdminUserService.delete_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# 관리자: 회원 권한(role) 변경
@extend_schema(
    tags=["Admin"],
    summary="관리자 - 회원 권한 변경",
    request=AdminUserRoleUpdateRequestSerializer,
    responses={200: AdminUserRoleUpdateResponseSerializer},
)
class AdminUserRoleUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request: Request, user_id: int, *args: Any, **kwargs: Any) -> Response:
        serializer = AdminUserRoleUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data["role"]

        user = AdminUserService.get_user(user_id)
        updated_user = AdminUserService.change_user_role(user, role)

        response_serializer = AdminUserRoleUpdateResponseSerializer(updated_user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
