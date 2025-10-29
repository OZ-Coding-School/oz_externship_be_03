from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth.models import AnonymousUser
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.views import ExceptionHandledAPIView
from apps.users.models.user import User
from apps.users.serializers.user_profile_serializers import (
    DupNicknameQuerySerializer,
    DupNicknameResponseSerializer,
    UserProfileSerializer,
)
from apps.users.views.responses import ok


class UserDupNicknameView(ExceptionHandledAPIView):
    """
    닉네임 중복 확인 API
    """

    permission_classes = [AllowAny]
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()

    @extend_schema(
        tags=["Users"],
        summary="닉네임 중복 확인",
        description="쿼리 파라미터로 전달된 'nickname'의 중복 여부 반환",
        request=None,
        responses={200: DupNicknameResponseSerializer},
        parameters=[
            OpenApiParameter(
                name="nickname",
                location=OpenApiParameter.QUERY,
                required=True,
                type=OpenApiTypes.STR,
                description="중복 여부를 확인할 닉네임",
            ),
            OpenApiParameter(
                name="case_insensitive",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.BOOL,
                description="대소문자 구분 여부, 구분안함=true (기본: true)",
            ),
        ],
    )
    def get(self, request: Request) -> Response:
        serializer = DupNicknameQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        nickname = serializer.validated_data["nickname"]
        case_insensitive = serializer.validated_data["case_insensitive"]

        filters_ = {"nickname__iexact": nickname} if case_insensitive else {"nickname": nickname}
        is_dup = User.objects.filter(**filters_).exists()

        return ok(
            "이미 사용중인 닉네임입니다." if is_dup else "사용 가능한 닉네임입니다.",
            data={"nickname": nickname, "available": not is_dup},
            status_code=status.HTTP_200_OK,
        )
from apps.users.serializers.user_profile_serializers import (
    UserProfilePasswordUpdateSerializer,
    UserProfileSerializer,
    UserProfileUpdateResponseSerializer,
    UserProfileUpdateSerializer,
)
from apps.users.services.user_profile_services import (
    change_password,
    update_user_profile,
)


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
        return Response(serializer.data, status=200)


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
