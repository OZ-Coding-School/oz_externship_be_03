from django.urls import path

from apps.users.views.admin_withdrawal_views import AdminWithdrawalListView

app_name = "users"

urlpatterns = [
    path(
        "admin/withdrawals",
        AdminWithdrawalListView.as_view(),
        name="admin_withdrawal_list",
    ),
]
