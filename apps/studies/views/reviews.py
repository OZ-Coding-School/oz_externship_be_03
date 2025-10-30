from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from django.db import IntegrityError
from django.db.models import Avg, Case, IntegerField, QuerySet, Sum, Value, When
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, permissions, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.lecture.models import RatingEnum
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.studies.models.reviews import Review
from apps.studies.permissions import IsGroupMemberDOP
from apps.studies.serializers.reviews import (
    ReviewCreateSerializer,
    ReviewListItemSerializer,
)


@extend_schema_view(
    get=extend_schema(
        operation_id="ListGroupReviews",
        parameters=[
            OpenApiParameter(name="page", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="page_size", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="정렬 키: `-created_at`(기본, 최신순) 또는 `created_at`(오래된순)",
            ),
            OpenApiParameter(
                name="rating",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="평점 필터(1~5). 예: rating=5",
            ),
        ],
        responses={200: ReviewListItemSerializer},
        tags=["StudyGroupReview"],
        summary="그룹 리뷰 목록",
        description="UUID로 지정된 스터디 그룹의 리뷰를 조회합니다.",
    ),
    post=extend_schema(
        operation_id="CreateReview",
        request=ReviewCreateSerializer,
        responses={
            201: OpenApiResponse(description="리뷰가 생성되었습니다."),
            401: OpenApiResponse(description="인증 필요"),
            403: OpenApiResponse(description="권한 없음(그룹 미가입 등)"),
            404: OpenApiResponse(description="대상 리소스 없음(예: study_group)"),
            409: OpenApiResponse(description="중복 리뷰 또는 무결성 충돌"),
            422: OpenApiResponse(description="검증 실패(필드/비즈니스 룰)"),
        },
        tags=["StudyGroupReview"],
        summary="그룹 리뷰 작성",
        description="경로의 group_id(UUID)를 사용해 해당 스터디 그룹에 리뷰를 생성합니다.",
        examples=[
            OpenApiExample(
                "create Review (no study_group in body)",
                value={"star_rating": 5, "content": "좋았어요!"},
                request_only=True,
            )
        ],
    ),
)
class GroupReviewListCreateView(generics.ListCreateAPIView[Review]):
    ordering: list[str] = ["-created_at"]

    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [permissions.IsAuthenticated(), IsGroupMemberDOP()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self) -> type[serializers.Serializer[Any]]:
        return ReviewCreateSerializer if self.request.method == "POST" else ReviewListItemSerializer

    def _parse_gid(self) -> UUID:
        raw = self.kwargs.get("group_id")
        try:
            return UUID(str(raw))
        except (TypeError, ValueError):
            raise ValidationError({"group_id": "유효한 UUID 형태의 group_id가 아닙니다."})

    def get_group_for_read(self) -> StudyGroup:
        gid = self._parse_gid()
        group = get_object_or_404(StudyGroup, uuid=gid)
        self.check_object_permissions(self.request, group)
        return group

    def get_group_for_write(self) -> StudyGroup:
        gid = self._parse_gid()
        return get_object_or_404(StudyGroup, uuid=gid)

    def get_queryset(self) -> QuerySet[Review]:
        group = self.get_group_for_read()
        qs = (
            Review.objects.filter(study_group_id=group.id)  # 내부 정수 PK
            .only("uuid", "star_rating", "content", "created_at", "updated_at", "user_id", "study_group_id")
            .order_by(*self.ordering)
        )

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

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group = self.get_group_for_read()
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            resp = self.get_paginated_response(serializer.data)
            resp.data["meta"] = {"group_id": str(group.uuid), **self._rating_stats(group.id)}
            return resp

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {"results": serializer.data, "meta": {"group_id": str(group.uuid), **self._rating_stats(group.id)}}
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        group = self.get_group_for_write()
        user_id = getattr(request.user, "pk", None)
        if user_id is None:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(data={**request.data, "study_group": group.pk}, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=422)

        try:
            # perform_create 대신 여기서 명시적으로 저장
            serializer.save()
        except IntegrityError:
            return Response({"detail": "이미 해당 스터디에 리뷰를 작성했습니다"}, status=status.HTTP_409_CONFLICT)

        return Response(status=status.HTTP_201_CREATED)

    def _rating_stats(self, group_pk: int) -> Dict[str, Any]:
        rating_int = Case(
            When(star_rating=RatingEnum.ONE, then=Value(1)),
            When(star_rating=RatingEnum.TWO, then=Value(2)),
            When(star_rating=RatingEnum.THREE, then=Value(3)),
            When(star_rating=RatingEnum.FOUR, then=Value(4)),
            When(star_rating=RatingEnum.FIVE, then=Value(5)),
            default=Value(0),
            output_field=IntegerField(),
        )
        qs = Review.objects.filter(study_group_id=group_pk)
        agg = qs.aggregate(
            avg=Avg(rating_int),
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
        avg = float(agg["avg"] or 0.0)
        return {
            "avg_rating": round(avg, 1),
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
