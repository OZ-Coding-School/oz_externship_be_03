from django.urls import path

from apps.users.views.admin_users_views import (
    AdminUserListView,
    AdminUserRoleUpdateView,
    AdminUserView,
)

app_name = "admin_users"

urlpatterns = [
    path("admin/users", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:user_id>", AdminUserView.as_view(), name="admin-user-detail"),
    path("admin/users/<int:user_id>/update_role", AdminUserRoleUpdateView.as_view(), name="admin-user-role-update"),
]
