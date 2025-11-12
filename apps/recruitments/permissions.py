from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.recruitments.models import Recruitment


class IsRecruitmentAuthor(permissions.BasePermission):
    """
    공고 작성자만 접근 가능한 권한
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        """로그인 여부 확인"""
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view: APIView, obj: Recruitment) -> bool:
        """공고 작성자 확인"""
        return obj.author == request.user
