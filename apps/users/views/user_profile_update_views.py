from django.contrib.auth.models import AnonymousUser
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.user_profile_serializers import (
    UserProfilePasswordUpdateSerializer,
    UserProfileUpdateResponseSerializer,
    UserProfileUpdateSerializer,
)
from apps.users.services.user_profile_update_services import (
    change_password,
    update_user_profile,
)


class UserProfileUpdateView(APIView):
    @extend_schema(
        tags=["Users"],
        summary="내 정보 수정 - 일반정보 수정 ",
        description="로그인한 사용자가 일반정보(프로필 이미지, 닉네임, 휴대전화 번호) 중 원하는 정보를 수정합니다. 휴대폰 정보를 수정하기 위해서는 휴대폰 인증을 수행해야 합니다.",
        request=UserProfileUpdateSerializer,
        responses=inline_serializer(
            name="PhoneVerificationSendCodeResponse",
            fields={
                "detail": serializers.CharField(),
                "data": UserProfileUpdateResponseSerializer(),
            },
        ),
    )
    def patch(self, request: Request) -> Response:
        # mypy용 명시
        if isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
            raise NotAuthenticated("인증이 필요합니다.")

        # instance를 넘겨 UniqueValidator가 본인을 제외하도록 함
        req_serializer = UserProfileUpdateSerializer(instance=request.user, data=request.data, partial=True)
        if not req_serializer.is_valid():
            # UniqueValidator 400 -> 메시지 기반 409 승격
            errors = req_serializer.errors
            dup_msgs = {"이미 사용 중인 휴대폰 번호입니다.", "이미 사용 중인 닉네임입니다."}
            flat = {str(msg) for v in errors.values() for msg in (v if isinstance(v, (list, tuple)) else [v])}
            if dup_msgs & flat:
                return Response({"error": list(dup_msgs & flat)[0]}, status=status.HTTP_409_CONFLICT)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        updated = update_user_profile(
            user=request.user,
            nickname=req_serializer.validated_data.get("nickname"),
            profile_img_url=req_serializer.validated_data.get("profile_img_url"),
            phone_number=req_serializer.validated_data.get("phone_number"),
            verify_token=req_serializer.validated_data.get("verify_token"),
        )

        resp_serializer = UserProfileUpdateResponseSerializer(updated)
        return Response(
            {"detail": "내 정보가 수정되었습니다.", "data": resp_serializer.data},
            status=status.HTTP_200_OK,
        )


class UserChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "change-password"  # 레이트리밋 스코프

    @extend_schema(
        tags=["Users"],
        summary="내 정보 수정 - 비밀번호 수정 ",
        description="로그인한 사용자가 비밀번호를 변경합니다.",
        request=UserProfilePasswordUpdateSerializer,
    )
    def patch(self, request: Request) -> Response:
        # mypy용 명시
        if isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
            raise NotAuthenticated("인증이 필요합니다.")

        serializer = UserProfilePasswordUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        change_password(
            user=request.user,
            current_password=serializer.validated_data.get("current_password"),
            new_password=serializer.validated_data["new_password"],
            new_password_confirm=serializer.validated_data["new_password_confirm"],
        )

        return Response({"detail": "비밀번호가 변경되었습니다."}, status=status.HTTP_200_OK)
