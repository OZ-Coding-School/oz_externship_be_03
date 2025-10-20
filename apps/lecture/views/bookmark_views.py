import random
from typing import Any, List, Optional, Sequence, Union

from django.db.models.query import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lecture.models import CrawledLecture
from apps.lecture.serializers.bookmark_serializers import LectureBookmarkSerializer


class PaginationHandlerMixin:
    """
    페이지네이션 기능 믹스인 클래스.
    - PageNumberPagination을 기본 페이지네이터 클래스로 사용.
    - paginator 인스턴스를 내부에서 캐싱하여 재사용.
    - DRF에서는 generic view에서 자동으로 페이지네이션을 지원하지만,
      APIView에선 이런 믹스인을 사용해 재활용.
    """

    pagination_class = PageNumberPagination
    _paginator: Optional[PageNumberPagination] = None  # 내부 paginator 객체 캐싱

    @property
    def paginator(self) -> Optional[PageNumberPagination]:
        """
        paginator 인스턴스를 반환.
        이미 생성된 객체가 없으면 pagination_class를 사용해 생성 후 캐싱.
        """
        if self._paginator is None:
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset: Union[QuerySet[Any], Sequence[Any]]) -> Optional[Sequence[Any]]:
        """
        쿼리셋 혹은 리스트를 페이지 단위로 분할하여 반환.

        :param queryset: QuerySet 또는 리스트 등 시퀀스 타입
        :return: 페이지네이션된 객체 리스트 또는 None (paginator가 없을 경우)

        mypy 타입 오류 방지를 위해 입력 타입을 Union[QuerySet, Sequence]로 넓혔고,
        paginate_queryset 호출 시 view=self 인자와 관련해 mypy가 타입 불일치 경고,
        현재 상황에서는 정상 동작을 위해 예외적으로 무시 처리(# type: ignore).
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)  # type: ignore[arg-type]

    def get_paginated_response(self, data: Any) -> Response:
        """
        페이지네이션된 데이터 포함한 Response 객체를 반환.

        DRF 시리얼라이저의 .data 속성은 ReturnDict나 ReturnList 타입이므로,
        mypy 충돌 방지를 위해 파라미터 타입을 Any로 처리.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

    @property
    def request(self) -> Request:
        """
        현재 뷰에 바인딩된 Request 객체를 반환.
        APIView에서는 self.request가 기본 제공되므로, 안전성 체크 후 반환.
        """
        if not hasattr(self, "request") or self.request is None:
            raise AttributeError("Request has not been set on the view.")
        return self.request


class LectureBookmarkListAPIView(APIView, PaginationHandlerMixin):
    """
    북마크된 강의 목록 조회 API 뷰로 페이지네이션 지원.

    - 권한은 AllowAny로 임시 설정되어 있으며, 실제 서비스 시 인증/권한 설정을 적용 필요.
    - Mock 데이터를 생성해 페이지네이션 및 직렬화 과정을 시연.
    - 추후 ORM QuerySet을 반환하도록 변경 필요,
      select_related, prefetch_related를 사용해 N+1 문제를 방지 예정.
    """

    permission_classes = [AllowAny]  # TODO: 기능 구현 후 권한 변경
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["Lectures"],
        summary="북마크한 강의 목록 조회 API",
        responses={200: LectureBookmarkSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        # Mock 데이터: CrawledLecture 인스턴스 50개를 리스트로 생성 (실제 DB가 아닌 임시 예제)
        mock_lectures: List[Any] = [
            CrawledLecture(
                id=i,
                uuid=f"123e4567-e89b-12d3-a456-4266141740{i:02d}",
                title=f"Mock 강의 {i}",
                instructor="홍길동",
                thumbnail_img_url="https://example.com/thumb.jpg",
                difficulty="NORMAL",
                original_price=120000,
                discount_price=100000,
                platform="inflearn",
                average_rating=4.6,
                duration=90 + i,
                url_link="https://inflearn.com/course/mock",
                description="기초부터 배우는 파이썬",
            )
            for i in range(1, 51)
        ]

        # 페이지네이션 처리: 쿼리셋/리스트를 페이지 단위로 잘라 반환
        page = self.paginate_queryset(mock_lectures)
        if page is not None:
            # 페이지네이션된 데이터만 직렬화
            serializer = LectureBookmarkSerializer(page, many=True)
            # 타입 불일치 문제를 회피하기 위해 get_paginated_response에 전달 시
            # serializer.data 자체를 넘겨도 무방 (Any 타입으로 처리)
            return self.get_paginated_response(serializer.data)

        # 페이지네이터가 없거나 pagination 대상이 아닐 경우 전체 데이터 직렬화 후 반환
        serializer = LectureBookmarkSerializer(mock_lectures, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LectureBookmarkButtonAPIView(APIView):
    """
    북마크 추가/삭제용 API 뷰.
    - mock 랜덤 응답으로 북마크가 추가되거나 삭제된 것처럼 처리.
    """

    permission_classes = [AllowAny]  # TODO: 기능 구현 후 권한 변경
    parser_classes = [parsers.JSONParser]

    @extend_schema(
        tags=["Lectures"],
        summary="북마크 추가/삭제 API (Mock 랜덤 응답)",
    )
    def post(self, request: Request, lecture_id: int) -> Response:
        # 랜덤으로 추가 또는 삭제 응답 발생
        if random.choice([True, False]):
            return Response({"detail": "북마크가 추가되었습니다."}, status=status.HTTP_201_CREATED)
        else:
            return Response({"detail": "북마크가 삭제되었습니다."}, status=status.HTTP_200_OK)
