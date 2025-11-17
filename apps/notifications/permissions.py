from typing import cast

from rest_framework.permissions import DjangoObjectPermissions
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.notifications.models import Notification
from apps.users.models import User


class IsNotificationOwner(DjangoObjectPermissions):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Notification) -> bool:
        return obj.user == cast(User, request.user)
