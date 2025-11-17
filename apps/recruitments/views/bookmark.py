from __future__ import annotations

from typing import Any, cast

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.recruitments.models import Recruitment
from apps.recruitments.serializers.bookmark import BookmarkToggleSerializer
from apps.recruitments.serializers.recruitments import RecruitmentListSerializer
from apps.recruitments.services.bookmark import (
    get_bookmarked_recruitments,
    toggle_bookmark,
)
from apps.users.models import User


@extend_schema(tags=["Recruitments"], summary="스터디 구인 공고 북마크 추가 / 삭제")
class RecruitmentBookmarkToggleAPIView(generics.GenericAPIView):  # type: ignore[type-arg]
    """
    REQ-RECM-010 — 북마크 추가 or 삭제
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BookmarkToggleSerializer
    lookup_field = "uuid"
    lookup_url_kwarg = "recruitment_uuid"

    def post(self, request: Request, recruitment_uuid: str, *args: Any, **kwargs: Any) -> Response:
        """POST /api/v1/recruitments/bookmarks/{recruitment_uuid}/ — 북마크 토글"""
        from django.shortcuts import get_object_or_404

        recruitment = get_object_or_404(Recruitment, uuid=recruitment_uuid)

        user: User = cast(User, request.user)
        is_bookmarked: bool = toggle_bookmark(recruitment, user)
        data = {
            "recruitment_uuid": str(recruitment.uuid),
            "is_bookmarked": is_bookmarked,
            "message": "북마크가 추가되었습니다." if is_bookmarked else "북마크가 해제되었습니다.",
        }
        serializer = self.get_serializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=["Recruitments"], summary="북마크한 스터디 구인 공고 목록 조회")
class RecruitmentBookmarkedListAPIView(generics.ListAPIView):  # type: ignore[type-arg]
    """REQ-RECM-011 — 북마크 목록 조회"""

    permission_classes = [IsAuthenticated]
    serializer_class = RecruitmentListSerializer

    def get_queryset(self) -> Any:
        """현재 로그인한 사용자의 북마크 목록을 반환"""
        user: User = cast(User, self.request.user)
        return get_bookmarked_recruitments(user)

    def get_serializer_context(self) -> dict[str, Any]:
        """Serializer context 반환"""
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx
