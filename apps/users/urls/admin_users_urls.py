from django.urls import path

from apps.users.views.admin_users_views import (
    AdminUserListView,
    AdminUserRoleUpdateView,
    AdminUserView,
)

app_name = "admin_users"

urlpatterns = [
    path("", AdminUserListView.as_view(), name="admin-user-list"),
    path("<int:user_id>", AdminUserView.as_view(), name="admin-user-detail"),
    path("<int:user_id>/update_role", AdminUserRoleUpdateView.as_view(), name="admin-user-role-update"),
]
