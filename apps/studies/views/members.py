from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
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
    queryset = StudyGroup.objects.all()

    def get_object(self, group_uuid: str) -> StudyGroup:
        return StudyGroup.objects.get(uuid=group_uuid)

    def delete(self, request: Request, group_uuid: str, member_id: int) -> Response:
        study_group = self.get_object(group_uuid)

        # Object-level permission 검사 (멤버 아님 → 403 / 리더 아님 → 400 가능)
        self.check_object_permissions(request, study_group)

        MemberService.kick_member(
            study_group=study_group,
            target_member_id=member_id,
        )
        return Response({"detail": "멤버가 추방되었습니다."}, status=status.HTTP_200_OK)


@extend_schema(
    operation_id="v1_studies_groups_leave_member",
    tags=["StudyGroup"],
    summary="스터디 탈퇴 API (REQ-STDY-007)",
    request=MemberLeaveSerializer,
)
class MemberLeaveView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]
    queryset = StudyGroup.objects.all()

    def get_object(self, group_uuid: str) -> StudyGroup:
        return StudyGroup.objects.get(uuid=group_uuid)

    def delete(self, request: Request, group_uuid: str) -> Response:
        study_group = self.get_object(group_uuid)
        self.check_object_permissions(request, study_group)

        try:
            MemberService.leave_group(user=request.user, study_group=study_group)
            return Response({"detail": "스터디에서 탈퇴했습니다."}, status=status.HTTP_200_OK)

        except ValidationError as e:
            detail = str(e.detail[0] if isinstance(e.detail, list) else e.detail)
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id="v1_studies_groups_delegate_leader",
    tags=["StudyGroup"],
    summary="스터디 리더 위임 API (REQ-STDY-008)",
    request=DelegateLeaderSerializer,
    responses={200: DelegateLeaderSerializer},
)
class DelegateLeaderView(APIView):
    permission_classes = [IsAuthenticated, IsGroupLeader]
    queryset = StudyGroup.objects.all()

    def get_object(self, group_uuid: UUID) -> StudyGroup:
        return StudyGroup.objects.get(uuid=group_uuid)

    def post(self, request: Request, group_uuid: UUID) -> Response:
        serializer = DelegateLeaderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        study_group = self.get_object(group_uuid)

        # Object-level permission 검사
        self.check_object_permissions(request, study_group)

        target_member_uuid = serializer.validated_data["target_member_uuid"]
        data = MemberService.delegate_leader(
            study_group=study_group,
            target_member_uuid=target_member_uuid,
        )

        return Response(data, status=status.HTTP_200_OK)
