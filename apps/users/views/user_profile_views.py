from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.user_profile_serializers import UserProfileSerializer


class MeView(APIView):
    """
    내 정보 조회 API
    - GET /api/v1/me
    - 로그인한 사용자의 프로필 정보를 반환
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Users"],
        summary="내 정보 조회",
        description="로그인한 사용자가 본인 정보를 조회한다.",
        responses=UserProfileSerializer,
    )
    def get(self, request: Request) -> Response:
        """
        현재 로그인한 사용자 정보 반환
        """
        serializer = UserProfileSerializer(request.user)
        return Response({"detail": "내 정보를 조회합니다.", "data": serializer.data})
