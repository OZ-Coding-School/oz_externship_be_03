from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
from apps.studies.permissions import IsGroupLeader
from apps.studies.serializers.members import (
    DelegateLeaderSerializer,
    KickMemberSerializer,
    LeaveGroupSerializer,
)
from apps.studies.services.members import MemberService


# REQ-STDY-006: 리더 위임 API
class MemberKickAPIView(APIView):
    """REQ-STDY-006: 스터디 그룹 멤버 추방 API"""

    serializer_class = KickMemberSerializer
    permission_classes = [IsAuthenticated, IsGroupLeader]

    @extend_schema(
        tags=["StudyGroup"],
        summary="스터디 그룹 멤버 추방 API",
        description="리더가 특정 멤버를 스터디 그룹에서 추방합니다. (REQ-STDY-006)",
        responses={
            200: {
                "type": "object",
                "example": {
                    "status": 200,
                    "message": "스터디 그룹 멤버를 추방했습니다.",
                },
            },
            400: {
                "type": "object",
                "example": {
                    "status": 400,
                    "message": "잘못된 요청이거나 필수 항목이 비어있습니다.",
                    "error": {
                        "code": "INVALID_ID_FORMAT",
                        "detail": "URL에 ID 형식이 아닌 값을 입력했습니다.",
                    },
                },
            },
            401: {
                "type": "object",
                "example": {
                    "status": 401,
                    "message": "로그인이 필요하거나 토큰 인증에 실패했습니다.",
                    "error": {
                        "code": "LOGIN_REQUIRED",
                        "detail": "로그인이 필요합니다.",
                    },
                },
            },
            403: {
                "type": "object",
                "example": {
                    "status": 403,
                    "message": "접근 권한이 없습니다.",
                    "error": {
                        "code": "LEADER_PERMISSION_REQUIRED",
                        "detail": "리더만 접근 가능한 기능입니다.",
                    },
                },
            },
            404: {
                "type": "object",
                "example": {
                    "status": 404,
                    "message": "페이지를 찾을 수 없습니다.",
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "detail": "해당 ID 값의 유저가 존재하지 않습니다.",
                    },
                },
            },
            500: {
                "type": "object",
                "example": {
                    "status": 500,
                    "message": "예기치 못한 서버 에러가 발생했습니다.",
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "detail": "예기치 못한 서버 에러가 발생했습니다.",
                    },
                },
            },
        },
    )
    def delete(self, request: Request, group_id: int, member_id: int) -> Response:
        """리더가 스터디 그룹에서 멤버를 추방하는 API"""
        # Mock group 생성
        mock_group = StudyGroup(id=group_id, name="Mock Study Group")

        # 요청 검증 (본문 없음)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 비즈니스 로직 실행 (Mock)
        MemberService.kick_member(mock_group, member_id)

        # 성공 응답 반환
        return Response(
            {"status": 200, "message": "스터디 그룹 멤버를 추방했습니다."},
            status=status.HTTP_200_OK,
        )


# REQ-STDY-007: 스터디 그룹 자진 탈퇴 API
class MemberLeaveAPIView(APIView):
    serializer_class = LeaveGroupSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["StudyGroup"],
        summary="스터디 그룹 자진 탈퇴 API",
        description="사용자가 자신이 속한 스터디 그룹을 자진 탈퇴합니다. (REQ-STDY-007)",
        request=LeaveGroupSerializer,
        responses={
            200: {
                "type": "object",
                "example": {
                    "status": 200,
                    "message": "스터디 그룹에서 탈퇴했습니다.",
                },
            },
            400: {
                "example": {
                    "status": 400,
                    "message": "잘못된 요청이거나 필수 항목이 비어있습니다.",
                    "error": {
                        "code": "INVALID_ID_FORMAT",
                        "detail": "URL에 ID 형식이 아닌 값을 입력했습니다.",
                    },
                },
            },
            401: {
                "example": {
                    "status": 401,
                    "message": "로그인이 필요하거나 토큰 인증에 실패했습니다.",
                    "error": {
                        "code": "LOGIN_REQUIRED",
                        "detail": "로그인이 필요합니다.",
                    },
                },
            },
            403: {
                "example": {
                    "status": 403,
                    "message": "접근 권한이 없습니다.",
                    "error": {
                        "code": "MEMBER_PERMISSION_REQUIRED",
                        "detail": "스터디 그룹 멤버만 접근 가능한 기능입니다.",
                    },
                },
            },
            404: {
                "example": {
                    "status": 404,
                    "message": "페이지를 찾을 수 없습니다.",
                    "error": {
                        "code": "STUDY_GROUP_NOT_FOUND",
                        "detail": "해당 UUID 값의 스터디 그룹이 존재하지 않습니다.",
                    },
                },
            },
            409: {
                "example": {
                    "status": 409,
                    "message": "요청과 현재 상태에 충돌이 있습니다.",
                    "error": {
                        "code": "LEADER_DELEGATION_REQUIRED",
                        "detail": "리더를 위임하지 않으면 탈퇴할 수 없습니다.",
                    },
                },
            },
            500: {
                "example": {
                    "status": 500,
                    "message": "예기치 못한 서버 에러가 발생했습니다.",
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "detail": "예기치 못한 서버 에러가 발생했습니다.",
                    },
                },
            },
        },
    )
    def delete(self, request: Request, group_id: int) -> Response:
        """로그인된 사용자가 자신이 속한 스터디 그룹을 탈퇴하는 API"""
        mock_group = StudyGroup(id=group_id, name="Mock Study Group")

        # 요청 본문 검증
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 로그인된 사용자 ID (mypy 타입 힌트 보정)
        user_id = cast(int, request.user.id)

        # 비즈니스 로직 실행
        MemberService.leave_group(mock_group, user_id)

        return Response(
            {"status": 200, "message": "스터디 그룹에서 탈퇴했습니다."},
            status=status.HTTP_200_OK,
        )


# REQ-STDY-008: 리더 위임 API
class DelegateLeaderAPIView(APIView):
    serializer_class = DelegateLeaderSerializer
    permission_classes = [IsAuthenticated, IsGroupLeader]
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["StudyGroup"],
        summary="스터디 그룹 리더 위임 API",
        description="리더가 특정 멤버에게 리더 권한을 위임합니다.",
        request=DelegateLeaderSerializer,
        responses={
            200: {"example": {"status": 200, "message": "스터디 그룹의 리더를 위임했습니다."}},
            403: {
                "example": {
                    "status": 403,
                    "message": "접근 권한이 없습니다.",
                    "error": {"code": "LEADER_PERMISSION_REQUIRED", "detail": "리더만 접근 가능한 기능입니다."},
                }
            },
        },
    )
    def post(self, request: Request, group_id: int) -> Response:
        # 실제 DB 대신 mock 객체 사용
        mock_group = StudyGroup(id=group_id, name="Mock Study Group")

        # 요청 데이터 검증
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        # 리더 위임 서비스 실행
        MemberService.delegate_leader(
            mock_group,
            serializer.validated_data["target_user_id"],
        )
        # 성공 응답
        return Response(
            {"status": 200, "message": "스터디 그룹의 리더를 위임했습니다."},
            status=status.HTTP_200_OK,
        )
