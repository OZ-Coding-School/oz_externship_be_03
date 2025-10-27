from typing import Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from apps.users.permissions import EmailVerifiedPermission
from apps.users.serializers.user_withdrawal_serializers import (
    UserAccountRecoverySerializer,
    UserWithdrawalsSerializer,
)
from apps.users.services import user_withdrawal_services


class UserWithdrawalAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Users"],
        summary="회원 탈퇴",
        description="로그인한 사용자가 회원 탈퇴 요청을 합니다.",
        request=UserWithdrawalsSerializer,
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)

        serializer = UserWithdrawalsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_withdrawal_services.withdraw(
            user=user,
            reason=serializer.validated_data["reason"],
            reason_detail=serializer.validated_data["reason_detail"],
        )

        return Response({"detail": "계정이 비활성화되었습니다."}, status=status.HTTP_200_OK)

        # TODO : 로그아웃 기능 가져오기
        # 서버사이드 로그아웃 (토큰 무효화 + 쿠키 삭제)
        # try:
        #     invalidate_user_tokens(request.user, request=request)
        # finally:
        #     clear_auth_cookies(response)
        #     return Response({"detail": "계정이 비활성화되었습니다."}, status=status.HTTP_200_OK)


class UserAccountRecoveryAPIView(APIView):
    permission_classes = [EmailVerifiedPermission]

    @extend_schema(
        tags=["Users"],
        summary="탈퇴 계정 복구",
        description="탈퇴 요청 상태의 사용자가 이메일 인증을 거친 뒤 계정 복구를 진행합니다.",
        request=UserAccountRecoverySerializer,
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = UserAccountRecoverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        claims = getattr(request, "email_verify_claims")
        user_withdrawal_services.recover_account(claims=claims)

        return Response({"detail": "계정 복구가 완료되었습니다."}, status=status.HTTP_200_OK)
