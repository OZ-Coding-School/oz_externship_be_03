from __future__ import annotations

from typing import Any, Dict, cast
from uuid import UUID

from django.db import IntegrityError
from django.db.models import (
    Avg,
    Case,
    FloatField,
    IntegerField,
    QuerySet,
    Sum,
    Value,
    When,
)
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import filters, generics, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models.review import RatingEnum
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.studies.models.reviews import Review
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
    def post(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        study_group = get_object_or_404(StudyGroup, id=group_id)

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


def _assert_group_member_or_403(group_id: int, user_id: int) -> None:
    is_member = GroupMember.objects.filter(
        study_group_id=group_id,
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
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReviewListItemSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_group(self) -> StudyGroup:
        return get_object_or_404(StudyGroup, pk=self.kwargs["group_id"])

    def _rating_stats(self, group_id: int) -> Dict[str, Any]:
        rating_int = Case(
            When(star_rating=RatingEnum.ONE, then=Value(1)),
            When(star_rating=RatingEnum.TWO, then=Value(2)),
            When(star_rating=RatingEnum.THREE, then=Value(3)),
            When(star_rating=RatingEnum.FOUR, then=Value(4)),
            When(star_rating=RatingEnum.FIVE, then=Value(5)),
            default=Value(0),
            output_field=IntegerField(),
        )

        qs = Review.objects.filter(study_group_id=group_id)

        agg = qs.aggregate(
            avg=Avg(rating_int, output_field=FloatField()),
            c1=Sum(
                Case(When(star_rating=RatingEnum.ONE, then=Value(1)), default=Value(0), output_field=IntegerField())
            ),
            c2=Sum(
                Case(When(star_rating=RatingEnum.TWO, then=Value(1)), default=Value(0), output_field=IntegerField())
            ),
            c3=Sum(
                Case(When(star_rating=RatingEnum.THREE, then=Value(1)), default=Value(0), output_field=IntegerField())
            ),
            c4=Sum(
                Case(When(star_rating=RatingEnum.FOUR, then=Value(1)), default=Value(0), output_field=IntegerField())
            ),
            c5=Sum(
                Case(When(star_rating=RatingEnum.FIVE, then=Value(1)), default=Value(0), output_field=IntegerField())
            ),
        )

        avg = agg["avg"] or 0.0
        return {
            "avg_rating": round(float(avg), 1),  # 소수 1자리
            "count_total": int(
                (agg["c1"] or 0) + (agg["c2"] or 0) + (agg["c3"] or 0) + (agg["c4"] or 0) + (agg["c5"] or 0)
            ),
            "histogram": {
                "1": int(agg["c1"] or 0),
                "2": int(agg["c2"] or 0),
                "3": int(agg["c3"] or 0),
                "4": int(agg["c4"] or 0),
                "5": int(agg["c5"] or 0),
            },
        }

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group = self.get_group()
        queryset: QuerySet[Review] = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)

        stats: Dict[str, Any] = self._rating_stats(group.id)  # ← 평균/히스토그램

        if page is not None:
            response = self.get_paginated_response(serializer.data)
            # 페이지네이션 응답에 meta 추가
            response.data["meta"] = {"group_id": group.id, **stats}
            return response

        return Response(
            {
                "results": serializer.data,
                "meta": {"group_id": group.id, **stats},
            }
        )

    def get_queryset(self) -> QuerySet[Review]:
        group = self.get_group()
        user_id = cast(int, self.request.user.id)
        _assert_group_member_or_403(group_id=group.id, user_id=user_id)
        qs = Review.objects.filter(study_group_id=group.id)
        qs = qs.only(
            "id",
            "star_rating",
            "content",
            "created_at",
            "updated_at",
            "user_id" "study_group_id",
        )
        rating_str = self.request.query_params.get("rating")
        if rating_str:
            try:
                rating = int(rating_str)
            except ValueError:
                rating = None
            if rating in (1, 2, 3, 4, 5):
                qs = qs.filter(star_rating=rating)
        return qs
