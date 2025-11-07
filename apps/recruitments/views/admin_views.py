from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.admin_serializers import (
    AdminRecruitmentDetailSerializer,
    AdminRecruitmentSerializer,
)


class AdminRecruitmentListAPIView(APIView):
    """관리자용 스터디 구인 공고 목록 조회 (태그명, 마감 여부 필터 지원)"""

    permission_classes = [IsAdminUser]
    serializer_class = AdminRecruitmentSerializer

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 목록 조회",
        parameters=[
            OpenApiParameter(name="tag", type=str, description="태그명 필터"),
            OpenApiParameter(name="is_closed", type=bool, description="마감 여부 필터"),
        ],
        responses={200: AdminRecruitmentSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = Recruitment.objects.prefetch_related("tags", "author", "study_group")

        # 태그명 필터
        tag_name = request.query_params.get("tag")
        if tag_name:
            queryset = queryset.filter(tags__name__icontains=tag_name)

        # 마감 여부 필터
        is_closed_param = request.query_params.get("is_closed")
        if is_closed_param is not None:
            value = is_closed_param.strip().lower()
            if value in ("true", "1"):
                queryset = queryset.filter(is_closed=True)
            elif value in ("false", "0"):
                queryset = queryset.filter(is_closed=False)

        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


class AdminRecruitmentDetailAPIView(APIView):
    """관리자용 스터디 구인 공고 상세 조회 및 삭제"""

    permission_classes = [IsAdminUser]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]
    serializer_class = AdminRecruitmentDetailSerializer

    def get_object(self, recruitment_id: int) -> Recruitment | None:
        return Recruitment.objects.prefetch_related("tags", "author", "study_group").filter(id=recruitment_id).first()

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 상세 조회",
        responses={200: AdminRecruitmentDetailSerializer},
    )
    def get(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_id)
        if not recruitment:
            return Response({"detail": "해당 공고를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(recruitment)
        return Response(serializer.data)

    @extend_schema(
        tags=["AdminRecruitments"],
        summary="관리자용 스터디 구인공고 삭제",
        responses={204: None, 404: {"detail": "해당 공고를 찾을 수 없습니다."}},
    )
    def delete(self, request: Request, recruitment_id: int, *args: Any, **kwargs: Any) -> Response:
        recruitment = self.get_object(recruitment_id)
        if not recruitment:
            return Response({"detail": "해당 공고를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        recruitment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
