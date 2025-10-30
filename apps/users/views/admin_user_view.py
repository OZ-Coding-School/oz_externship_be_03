# apps/users/views/admin_withdrawals_view.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models.withdrawal import Withdrawal
from apps.users.serializers.admin_user_serializer import (
    WithdrawalListResponseSerializer,
)


@extend_schema(
    tags=["Users"],
    operation_id="api_v1_admin_users_withdrawals_list",
    summary="관리자 탈퇴 회원 목록 조회",
    responses=WithdrawalListResponseSerializer,
)
class AdminWithdrawalListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request: Request) -> Response:
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 20))
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        reason = request.query_params.get("reason")
        keyword = request.query_params.get("keyword")

        withdrawals = Withdrawal.objects.select_related("user").all()

        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                withdrawals = withdrawals.filter(
                    created_at__date__gte=start_dt,
                    created_at__date__lte=end_dt,
                )
            except ValueError:
                return Response(
                    {"error": "날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식 사용"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if reason:
            withdrawals = withdrawals.filter(reason__icontains=reason)

        if keyword:
            withdrawals = withdrawals.filter(user__name__icontains=keyword) | withdrawals.filter(
                user__email__icontains=keyword
            )

        total_count = withdrawals.count()

        if limit > 0:
            offset = (page - 1) * limit
            withdrawals = withdrawals[offset : offset + limit]

        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1

        withdrawal_list: List[Dict[str, Any]] = []
        for withdrawal in withdrawals:
            user = withdrawal.user
            if not user:
                continue

            withdrawal_list.append(
                {
                    "id": user.id,
                    "email": user.email,
                    "name": getattr(user, "name", ""),
                    "role": getattr(user, "role", ""),
                    "birthday": getattr(user, "birthday", None),
                    "reason": withdrawal.reason,
                    "withdrawn_at": withdrawal.created_at,
                }
            )

        page_info = {
            "page": page,
            "limit": limit,
            "total_items": total_count,
            "total_pages": total_pages,
        }

        serializer = WithdrawalListResponseSerializer({"users": withdrawal_list, "pagination": page_info})

        return Response(
            {
                "detail": "회원 탈퇴 내역 목록 조회에 성공하였습니다.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
