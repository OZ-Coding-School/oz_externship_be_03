from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import Category
from apps.lecture.serializers.category_serializers import CategoryListSerializer


class CategoryListView(APIView):

    serializer_class = CategoryListSerializer

    @extend_schema(
        operation_id="v1_category_list",
        tags=["Lectures"],
        summary="전체 카테고리 목록 조회 API",
        responses={200: CategoryListSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        categories = Category.objects.all()
        serializer = CategoryListSerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
