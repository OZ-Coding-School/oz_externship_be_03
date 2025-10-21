from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
from apps.studies.permissions import IsGroupLeader
from apps.studies.serializers.members import DelegateLeaderSerializer
from apps.studies.services.members import MemberService


# REQ-STDY-006: 리더 위임 API
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
