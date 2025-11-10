from django.urls import path

from apps.users.views.admin_dashboard_views import AdminWithdrawalReasonStatsView
from apps.users.views.admin_users_views import (
    AdminUserListView,
    AdminUserRoleUpdateView,
    AdminUserView,
)
from apps.users.views.admin_withdrawal_views import (
    AdminUserRestoreView,
    AdminWithdrawalListView,
)
from apps.users.views.withdrawal_trends_views import WithdrawalTrendsAPIView

app_name = "admin"

urlpatterns = [
    # --------------------------------------------------------
    # 어드민 유저 리스트 및 상세 조회, 수정, 삭제
    # --------------------------------------------------------
    path("admin/users", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:user_id>", AdminUserView.as_view(), name="admin-user-detail"),
    path("admin/users/<int:user_id>/update_role", AdminUserRoleUpdateView.as_view(), name="admin-user-role-update"),
    # --------------------------------------------------------
    # 어드민 탈퇴 유저 관리
    # --------------------------------------------------------
    path(
        "admin/withdrawals",
        AdminWithdrawalListView.as_view(),
        name="admin_withdrawal_list",
    ),
    path(
        "admin/users/<int:user_id>/restore",
        AdminUserRestoreView.as_view(),
        name="admin_user_restore",
    ),
    # --------------------------------------------------------
    # 어드민 대시보드
    # --------------------------------------------------------
    path(
        "admin/dashboard/withdrawals/trends",
        WithdrawalTrendsAPIView.as_view(),
        name="withdrawal_trends",
    ),
    path(
        "admin/dashboard/withdrawals/stats",
        AdminWithdrawalReasonStatsView.as_view(),
        name="admin_withdrawal_list_by_reason",
    ),  # 회원 탈퇴 사유 추적
]
