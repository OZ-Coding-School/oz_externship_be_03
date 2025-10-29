from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import IntegrityError
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import filters, generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import RatingEnum
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.studies.models.reviews import Review
from apps.studies.permissions import IsGroupMemberDOP
from apps.studies.serializers.reviews import (
    ReviewCreateSerializer,
    ReviewListItemSerializer,
)


class ReviewCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="CreateReview",
        request=ReviewCreateSerializer,
        responses={
            201: OpenApiResponse(description="리뷰가 생성되었습니다."),
            401: OpenApiResponse(description="인증 필요"),
            403: OpenApiResponse(description="권한 없음"),
            404: OpenApiResponse(description="대상 리소스 없음(예: study_group)"),
            409: OpenApiResponse(description="중복 리뷰 또는 무결성 충돌"),
            422: OpenApiResponse(description="검증 실패(필드/비즈니스 룰"),
        },
        tags=["StudyGroupReview"],
        summary="리뷰 작성",
        description="경로의 group_id를 사용해 해당 스터디 그룹에 리뷰를 생성합니다.",
        examples=[
            OpenApiExample(
                "create Review (no study_group in body)",
                value={"star_rating": 5, "content": "좋았어요!"},
                request_only=True,
            )
        ],
    )
    def post(self, request: Request, group_id: UUID, *args: Any, **kwargs: Any) -> Response:
        # URL에서 받은 UUID로 StudyGroup 조회 (내부적으로는 id 사용)
        study_group = get_object_or_404(StudyGroup, uuid=group_id)

        user_id = getattr(request.user, "pk", None)
        if user_id is None:
            return Response(status=401)

        if Review.objects.filter(user_id=user_id, study_group=study_group).exists():
            return Response({"detail": "이미 해당 스터디에 리뷰를 작성했습니다"}, status=409)

        data = {"study_group": study_group.pk, **request.data}
        serializer = ReviewCreateSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=422)

        try:
            serializer.save()
        except IntegrityError:
            return Response({"detail": "이미 해당 스터디에 리뷰를 작성했습니다"}, status=409)

        return Response(status=201)


def _assert_group_member_or_403(group_id: UUID, user_id: int) -> None:
    # UUID로 StudyGroup을 찾아서 내부 id로 멤버십 확인
    study_group = get_object_or_404(StudyGroup, uuid=group_id)
    is_member = GroupMember.objects.filter(
        study_group_id=study_group.id,  # 내부적으로는 id 사용
        user_id=user_id,
    ).exists()
    if not is_member:
        raise PermissionDenied("이 그룹의 멤버만 리뷰를 볼 수 있습니다.")


@extend_schema(
    operation_id="ListGroupReviews",
    tags=["StudyGroupReview"],
    parameters=[
        OpenApiParameter(name="page", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
        OpenApiParameter(name="page_size", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="정렬 키: `-created_at'(기본, 최신순) 또는 'created_at`(오래된순)",
        ),
        OpenApiParameter(
            name="rating",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="평점 필터(1~5). 예: rating=5",
        ),
    ],
    responses={200: ReviewListItemSerializer},
)
class GroupReviewListView(generics.ListAPIView[Review]):
    permission_classes = [permissions.IsAuthenticated, IsGroupMemberDOP]
    serializer_class = ReviewListItemSerializer
    ordering = ["-created_at"]

    def _parse_gid(self) -> UUID:
        raw = self.kwargs.get("group_id")
        try:
            return UUID(str(raw))
        except (TypeError, ValueError):
            # 400: 잘못된 형식
            raise ValidationError({"group_id": "유효한 UUID 형태의 group_id가 아닙니다."})

    def get_group(self) -> StudyGroup:
        gid = self._parse_gid()
        # 404: 그룹 없음 (UUID로 조회)
        group = get_object_or_404(StudyGroup, uuid=gid)
        # 403: 비멤버 → 권한 클래스에서 검사
        self.check_object_permissions(self.request, group)
        return group

    def get_queryset(self) -> QuerySet[Review]:
        group = self.get_group()

        qs = (
            Review.objects.filter(study_group_id=group.id)  # 내부적으로는 id 사용
            # serializer.get_is_mine()에서 obj.user_id 비교하므로 user_id 필요
            .only("uuid", "star_rating", "content", "created_at", "updated_at", "user_id")
        )

        # ?rating=1..5 → Enum 매핑 후 필터
        rating_str = self.request.query_params.get("rating")
        if rating_str:
            try:
                rating = int(rating_str)
            except ValueError:
                rating = None
            if rating in (1, 2, 3, 4, 5):
                rating_map = {
                    1: RatingEnum.ONE,
                    2: RatingEnum.TWO,
                    3: RatingEnum.THREE,
                    4: RatingEnum.FOUR,
                    5: RatingEnum.FIVE,
                }
                qs = qs.filter(star_rating=rating_map[rating])

        return qs
