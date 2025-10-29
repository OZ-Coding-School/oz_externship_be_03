# apps/users/urls/admin_withdrawals_urls.py
from django.urls import path

from apps.users.views.admin_user_view import AdminWithdrawalListView

app_name = "users"  # ✅ 추가

urlpatterns = [
    path(
        "admin/users/withdrawals/",
        AdminWithdrawalListView.as_view(),
        name="admin_withdrawal_list",
    ),
]
