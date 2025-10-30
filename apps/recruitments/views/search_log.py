from datetime import timedelta
from typing import Any, List

from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.search_log import SearchLog
from apps.recruitments.serializers.search_log import SearchLogSerializer


class SearchLogAPIView(APIView):
    serializer_class = SearchLogSerializer
    permission_classes = [AllowAny]

    @extend_schema(tags=["SearchLogs"], summary="검색 기록 등록")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = request.user if isinstance(request.user, AbstractUser) else None
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["SearchLogs"], summary="검색 기록 조회", responses={200: SearchLogSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = request.user if isinstance(request.user, AbstractUser) else None
        mock_data: List[SearchLog] = [
            SearchLog(
                id=i,
                user=user,
                q=f"검색어 {i}",
                filters={"status": "OPEN"},
                results_count=10 + i,
                latency_ms=50 + i,
                ip="127.0.0.1",
                user_agent="Mozilla/5.0",
                created_at=timezone.now() - timedelta(hours=i),
            )
            for i in range(1, 6)
        ]
        serializer = self.serializer_class(instance=mock_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
