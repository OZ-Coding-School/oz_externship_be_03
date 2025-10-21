from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.studies.models.groups import GroupMember, StudyGroup
from apps.studies.serializers.members import LeaderDelegationSerializer


class LeaderDelegationAPIView(UpdateAPIView[Any]):
    """REQ-STDY-006: 스터디 그룹 리더 위임 API"""

    serializer_class = LeaderDelegationSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Study Member"],
        summary="스터디 그룹 리더 위임 API",
        description="리더가 특정 멤버에게 리더 권한을 위임합니다.",
        responses={
            200: {"type": "object", "example": {"status": 200, "message": "스터디 그룹의 리더를 위임했습니다."}},
            403: {
                "type": "object",
                "example": {
                    "status": 403,
                    "message": "접근 권한이 없습니다.",
                    "error": {"code": "LEADER_PERMISSION_REQUIRED", "detail": "리더만 접근 가능한 기능입니다."},
                },
            },
        },
    )
    # 목데이터
    def patch(self, request: Request, group_id: str, member_id: int) -> Response:
        mock_group = StudyGroup(id=group_id, name="Mock Study Group")
        mock_member = GroupMember(id=member_id, is_leader=False)

        serializer = self.serializer_class(mock_member, context={"request": request, "group": mock_group})
        serializer.validate({})  # mock validation

        mock_response: dict[str, Any] = {
            "status": 200,
            "message": "스터디 그룹의 리더를 위임했습니다.",
        }
        return Response(mock_response, status=status.HTTP_200_OK)
