from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models import Application
from apps.recruitments.permissions import IsRecruitmentAuthor
from apps.recruitments.serializers.application import ApplicationDetailSerializer, ApplicationListSerializer
from apps.studies.models.groups import GroupMember


class ApplicationListAPIView(APIView):
    """
    공고 작성자의 지원 내역 목록 조회 API
    """

    permission_classes = [IsRecruitmentAuthor]
    serializer_class = ApplicationListSerializer

    @extend_schema(
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
        responses={200: ApplicationListSerializer(many=True)},
    )
    def get(self, request: Request, recruitment_uuid: str) -> Response:
        """지원 내역 목록 조회"""
        from apps.recruitments.models import Recruitment

        # 공고 작성자 권한 확인
        recruitment = get_object_or_404(Recruitment, uuid=recruitment_uuid)
        self.check_object_permissions(request, recruitment)

        # 지원 내역 조회
        applications = Application.objects.filter(recruitment=recruitment).select_related("user").order_by("-created_at")

        # 페이지네이션
        from rest_framework.pagination import PageNumberPagination

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(applications, request)

        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ApplicationDetailAPIView(APIView):
    """
    공고 작성자의 지원 내역 상세 조회 API
    """

    permission_classes = [IsRecruitmentAuthor]
    serializer_class = ApplicationDetailSerializer

    @extend_schema(
        operation_id="retrieve_recruitment_application",
        summary="지원 내역 상세 조회",
        description="공고 작성자가 지원 내역의 상세 정보를 조회합니다.",
        tags=["Recruitments"],
        responses={200: ApplicationDetailSerializer},
    )
    def get(self, request: Request, recruitment_uuid: str, application_uuid: str) -> Response:
        """지원 내역 상세 조회"""
        from apps.recruitments.models import Recruitment

        # 공고 작성자 권한 확인
        recruitment = get_object_or_404(Recruitment, uuid=recruitment_uuid)
        self.check_object_permissions(request, recruitment)

        # 지원 내역 조회
        application = get_object_or_404(
            Application.objects.select_related("user"),
            recruitment=recruitment,
            uuid=application_uuid,
        )

        serializer = self.serializer_class(application)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ApplicationApproveAPIView(APIView):
    """
    공고 작성자의 지원 승인 API
    - REQ-APLY-004: 승인하기
    """

    permission_classes = [IsRecruitmentAuthor]

    @extend_schema(
        operation_id="approve_recruitment_application",
        summary="지원 승인",
        description="공고 작성자가 지원을 승인하고 스터디 그룹 멤버로 등록합니다.",
        tags=["Recruitments"],
        request=None,
        responses={
            200: {"description": "승인 완료"},
            400: {"description": "승인 불가"},
        },
    )
    def post(self, request: Request, recruitment_uuid: str, application_uuid: str) -> Response:
        """지원 승인 및 스터디 그룹 멤버 등록"""
        from apps.recruitments.models import Recruitment

        # 공고 작성자 권한 확인
        recruitment = get_object_or_404(Recruitment, uuid=recruitment_uuid)
        self.check_object_permissions(request, recruitment)

        # 지원 내역 조회
        application = get_object_or_404(Application, recruitment=recruitment, uuid=application_uuid)

        # 이미 승인되거나 거절된 항목 체크
        if application.status in ["APPROVED", "REJECTED"]:
            return Response({"detail": "이미 처리된 지원입니다."}, status=status.HTTP_400_BAD_REQUEST)

        study_group = recruitment.study_group

        if not study_group:
            return Response({"detail": "스터디 그룹이 존재하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 공고 모집 인원 체크
        approved_count = Application.objects.filter(recruitment=recruitment, status="APPROVED").count()

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


class ApplicationRejectAPIView(APIView):
    """
    공고 작성자의 지원 거절 API
    - REQ-APLY-005: 거절하기
    """

    permission_classes = [IsRecruitmentAuthor]

    @extend_schema(
        operation_id="reject_recruitment_application",
        summary="지원 거절",
        description="공고 작성자가 지원을 거절합니다.",
        tags=["Recruitments"],
        request=None,
        responses={
            200: {"description": "거절 완료"},
            400: {"description": "거절 불가"},
        },
    )
    def post(self, request: Request, recruitment_uuid: str, application_uuid: str) -> Response:
        """지원 거절"""
        from apps.recruitments.models import Recruitment

        # 공고 작성자 권한 확인
        recruitment = get_object_or_404(Recruitment, uuid=recruitment_uuid)
        self.check_object_permissions(request, recruitment)

        # 지원 내역 조회
        application = get_object_or_404(Application, recruitment=recruitment, uuid=application_uuid)

        # 이미 승인되거나 거절된 항목 체크
        if application.status in ["APPROVED", "REJECTED"]:
            return Response({"detail": "이미 처리된 지원입니다."}, status=status.HTTP_400_BAD_REQUEST)

        application.status = "REJECTED"
        application.save()

        return Response({"detail": "거절되었습니다."}, status=status.HTTP_200_OK)