from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models import Tag
from apps.recruitments.serializers.tag import TagSerializer


class TagPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class TagAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = TagSerializer
    pagination_class = TagPagination

    @extend_schema(
        tags=["Recruitments"],
        summary="공고에 사용되는 태그 목록 조회 API (검색기능 사용가능)",
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                description="태그 검색에 사용될 키워드를 입력하여 사용합니다. 태그 이름을 기준으로 검색됩니다.",
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                description="조회할 페이지의 숫자입니다.",
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                description="페이지 네이션 적용시 한 페이지에 가져올 항목의 수입니다. (max: 100)",
            ),
        ],
    )
    def get(self, request: Request) -> Response:
        queryset = self.get_queryset(request)
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(tags=["Recruitments"], summary="공고에 사용할 태그를 추가하는 API 입니다.")
    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)

    def get_queryset(self, request: Request) -> QuerySet[Tag]:
        queryset = Tag.objects.all().order_by("name")
        keyword = request.query_params.get("search")

        if keyword:
            queryset = queryset.filter(name__icontains=keyword)

        return queryset
