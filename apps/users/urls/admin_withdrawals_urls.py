from django.urls import path

from apps.users.views.admin_user_view import AdminWithdrawalListView

app_name = "users"

urlpatterns = [
    path(
        "admin/users/withdrawals/",
        AdminWithdrawalListView.as_view(),
        name="admin_withdrawal_list",
    ),
]
