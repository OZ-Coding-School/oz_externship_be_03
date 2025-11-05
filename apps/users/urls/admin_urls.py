from django.urls import path

from apps.users.views.admin_users_views import (
    AdminUserListView,
    AdminUserRoleUpdateView,
    AdminUserView,
)
from apps.users.views.admin_withdrawal_views import AdminWithdrawalListView

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
]
