from django.db import transaction
from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.recruitments.models import Application
from apps.recruitments.permissions import IsRecruitmentAuthor
from apps.recruitments.serializers.application import ApplicationDetailSerializer, ApplicationListSerializer
from apps.studies.models.groups import GroupMember


@extend_schema_view(
    list=extend_schema(
        operation_id="list_recruitment_applications",
        summary="지원 내역 목록 조회",
        description="공고 작성자가 특정 공고의 지원 내역 목록을 조회합니다.",
        tags=["Recruitments"],
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                description="페이지 번호",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                description="페이지당 항목 수",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        operation_id="retrieve_recruitment_application",
        summary="지원 내역 상세 조회",
        description="공고 작성자가 지원 내역의 상세 정보를 조회합니다.",
        tags=["Recruitments"],
    ),
)
class ApplicationViewSet(viewsets.ReadOnlyModelViewSet[Application]):
    """
    공고 작성자의 지원 내역 조회/승인/거절
    """

    permission_classes = [IsRecruitmentAuthor]
    lookup_field = "uuid"

    def get_queryset(self) -> QuerySet[Application]:
        """특정 공고의 지원 내역 조회"""
        recruitment_uuid = self.kwargs.get("recruitment_uuid")
        if not recruitment_uuid:
            return Application.objects.none()
        return Application.objects.filter(recruitment__uuid=recruitment_uuid).select_related("user", "recruitment")

    def get_serializer_class(self) -> type[ApplicationDetailSerializer] | type[ApplicationListSerializer]:
        """액션별 serializer 선택"""
        if self.action == "retrieve":
            return ApplicationDetailSerializer
        return ApplicationListSerializer

    def check_object_permissions(self, request: Request, obj: Application) -> None:
        """공고 작성자 권한 확인"""
        recruitment = obj.recruitment
        for permission in self.get_permissions():
            if not permission.has_object_permission(request, self, recruitment):
                self.permission_denied(request, message=getattr(permission, "message", None))

    @extend_schema(
        operation_id="approve_recruitment_application",
        summary="지원 승인",
        description="공고 작성자가 지원을 승인하고 스터디 그룹 멤버로 등록합니다.",
        tags=["Recruitments"],
        request=None,
        responses={200: {"description": "승인 완료"}, 400: {"description": "승인 불가"}},
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self) -> Response:
        """
        지원 승인 및 스터디 그룹 멤버 등록
        """
        application = self.get_object()

        # 이미 승인되거나 거절된 항목 체크
        if application.status in ["APPROVED", "REJECTED"]:
            return Response({"detail": "이미 처리된 지원입니다."}, status=status.HTTP_400_BAD_REQUEST)

        recruitment = application.recruitment
        study_group = recruitment.study_group

        if not study_group:
            return Response({"detail": "스터디 그룹이 존재하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 공고 모집 인원 체크
        approved_count = Application.objects.filter(
            recruitment=recruitment, status="APPROVED"
        ).count()

        if approved_count >= recruitment.expected_headcount:
            return Response({"detail": "모집 인원이 마감되었습니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 스터디 그룹 정원 체크
        current_member_count = study_group.members.count()
        if current_member_count >= study_group.max_headcount:
            return Response({"detail": "스터디 그룹 정원이 초과되었습니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 트랜잭션으로 승인 처리 및 멤버 등록
        with transaction.atomic():
            application.status = "APPROVED"
            application.save()

            GroupMember.objects.create(study_group=study_group, user=application.user, is_leader=False)

        return Response({"detail": "승인되었습니다."}, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="reject_recruitment_application",
        summary="지원 거절",
        description="공고 작성자가 지원을 거절합니다.",
        tags=["Recruitments"],
        request=None,
        responses={200: {"description": "거절 완료"}, 400: {"description": "거절 불가"}},
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self) -> Response:
        """
        지원 거절
        """
        application = self.get_object()

        # 이미 승인되거나 거절된 항목 체크
        if application.status in ["APPROVED", "REJECTED"]:
            return Response({"detail": "이미 처리된 지원입니다."}, status=status.HTTP_400_BAD_REQUEST)

        application.status = "REJECTED"
        application.save()

        return Response({"detail": "거절되었습니다."}, status=status.HTTP_200_OK)