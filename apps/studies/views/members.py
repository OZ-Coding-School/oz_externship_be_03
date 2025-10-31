from typing import Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.groups import StudyGroup
from ..permissions import IsGroupLeader, IsGroupMember
from ..serializers.members import (
    DelegateLeaderSerializer,
    MemberKickSerializer,
    MemberLeaveSerializer,
)
from ..services.members import MemberService


@extend_schema(
    operation_id="v1_studies_groups_kick_member",
    tags=["StudyGroup"],
    summary="스터디 멤버 추방 API (REQ-STDY-006)",
    request=MemberKickSerializer,
)
class MemberKickView(APIView):
    permission_classes = [IsAuthenticated, IsGroupLeader]

    def delete(self, request: Request, group_uuid: str, member_id: int, *args: Any, **kwargs: Any) -> Response:
        study_group = StudyGroup.objects.get(uuid=group_uuid)
        MemberService.kick_member(study_group, member_id)
        return Response({"detail": "멤버가 추방되었습니다."}, status=status.HTTP_200_OK)


@extend_schema(
    operation_id="v1_studies_groups_leave_member",
    tags=["StudyGroup"],
    summary="스터디 탈퇴 API (REQ-STDY-007)",
    request=MemberLeaveSerializer,
)
class MemberLeaveView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]

    def delete(self, request: Request, group_uuid: str, *args: Any, **kwargs: Any) -> Response:
        serializer = MemberLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not serializer.validated_data.get("confirm"):
            return Response({"detail": "탈퇴가 취소되었습니다."}, status=status.HTTP_400_BAD_REQUEST)

        study_group = StudyGroup.objects.get(uuid=group_uuid)
        MemberService.leave_group(study_group, cast(int, request.user.id))
        return Response({"detail": "스터디에서 탈퇴했습니다."}, status=status.HTTP_200_OK)


@extend_schema(
    operation_id="v1_studies_groups_delegate_leader",
    tags=["StudyGroup"],
    summary="스터디 리더 위임 API (REQ-STDY-008)",
    request=DelegateLeaderSerializer,
    responses={200: DelegateLeaderSerializer},
)
class DelegateLeaderView(APIView):
    permission_classes = [IsAuthenticated, IsGroupLeader]

    def post(self, request: Request, group_uuid: str, *args: Any, **kwargs: Any) -> Response:
        serializer = DelegateLeaderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_member_id = serializer.validated_data["target_member_id"]
        study_group = StudyGroup.objects.get(uuid=group_uuid)
        MemberService.delegate_leader(study_group, target_member_id)

        response_data = {
            "target_member_id": target_member_id,
            "previous_leader_id": request.user.id,
            "new_leader_id": target_member_id,
            "message": "리더가 성공적으로 위임되었습니다.",
        }
        return Response(DelegateLeaderSerializer(response_data).data, status=status.HTTP_200_OK)
