from django.urls import path

from apps.users.views.admin_users_views import (
    AdminUserListView,
    AdminUserRoleUpdateView,
    AdminUserView,
)
from apps.users.views.admin_withdrawal_views import AdminWithdrawalListView

app_name = "admin"

urlpatterns = [
    path("admin/users", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:user_id>", AdminUserView.as_view(), name="admin-user-detail"),
    path("admin/users/<int:user_id>/update_role", AdminUserRoleUpdateView.as_view(), name="admin-user-role-update"),
    path(
        "admin/withdrawals",
        AdminWithdrawalListView.as_view(),
        name="admin_withdrawal_list",
    ),
]
