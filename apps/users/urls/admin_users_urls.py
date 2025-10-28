from django.urls import path

from apps.users.views.admin_users_views import (
    AdminUserDeleteView,
    AdminUserDetailView,
    AdminUserListView,
    AdminUserRoleUpdateView,
    AdminUserUpdateView,
)

app_name = "users"

urlpatterns = [
    path("admin/", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/<int:user_id>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/<int:user_id>/update/", AdminUserUpdateView.as_view(), name="admin-user-update"),
    path("admin/<int:user_id>/delete/", AdminUserDeleteView.as_view(), name="admin-user-delete"),
    path("admin/<int:user_id>/role/", AdminUserRoleUpdateView.as_view(), name="admin-user-role-update"),
]
