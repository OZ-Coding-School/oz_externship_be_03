# apps/studies/views/specs/notes.py

from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import (
    AllowAny,  # 스펙 확인 편의를 위해 허용(실서비스시 IsAuthenticated 권장)
)
from rest_framework.response import Response
from rest_framework.views import APIView


# 학습 스펙용 Swagger 문서 전용 클래스
class StudyNoteSpecView(APIView):
    """
    [Spec API] 스터디노트 목록/작성 스펙 노출용 엔드포인트
    - 실제 기능은 없음
    - Swagger(스펙) 문서화를 위해 요청/응답 예시만 보여줌
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="스터디노트 목록 조회 (Spec)",
        description="특정 스터디 그룹의 학습 기록 목록을 반환합니다. (스펙용, 더미 응답)",
        responses={
            200: OpenApiResponse(
                description="성공적으로 노트 목록 반환",
                response={
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "example": 2},
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer", "example": 1},
                                    "title": {"type": "string", "example": "1주차 회의 요약"},
                                    "content": {"type": "string", "example": "오늘은 API 구조를 설계함"},
                                    "author": {"type": "string", "example": "안현기"},
                                    "created_at": {"type": "string", "example": "2025-10-22T09:00:00"},
                                },
                                "required": ["id", "title", "content", "author", "created_at"],
                            },
                        },
                    },
                    "required": ["count", "results"],
                },
            ),
        },
    )
    def get(self, request):
        """GET /spec/studies/notes/"""
        dummy_data = {
            "count": 2,
            "results": [
                {
                    "id": 1,
                    "title": "1주차 회의 요약",
                    "content": "오늘은 API 구조를 설계함",
                    "author": "안현기",
                    "created_at": "2025-10-22T09:00:00",
                },
                {
                    "id": 2,
                    "title": "2주차 코드 리뷰",
                    "content": "시리얼라이저 개선 및 테스트 코드 논의",
                    "author": "이형운",
                    "created_at": "2025-10-22T10:00:00",
                },
            ],
        }
        return Response(dummy_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="스터디노트 작성 (Spec)",
        description="노트 제목과 내용을 입력해 새 노트를 작성합니다. (스펙용, 더미 응답)",
        request={
            "type": "object",
            "properties": {
                "title": {"type": "string", "example": "1주차 회의 요약"},
                "content": {"type": "string", "example": "오늘은 API 구조를 설계함"},
            },
            "required": ["title", "content"],
        },
        responses={
            201: OpenApiResponse(description="노트 생성 완료"),
        },
    )
    def post(self, request):
        """POST /spec/studies/notes/"""
        title = request.data.get("title", "제목 없음")
        content = request.data.get("content", "내용 없음")

        dummy_response = {
            "title": title,
            "content": content,
            "message": "스터디노트 생성 스펙 성공 (더미 응답)",
        }
        return Response(dummy_response, status=status.HTTP_201_CREATED)


# 학습 Mock API (테스트용)
class StudyNoteListCreateAPIView(APIView):
    """학습 기록 전체조회(GET), 작성(POST) 테스트용"""

    permission_classes = [AllowAny]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    def get(self, request):
        """노트 목록 불러오기"""
        mock_data = [
            {"id": 1, "title": "테스트노트1", "content": "내용1"},
            {"id": 2, "title": "테스트노트2", "content": "내용2"},
        ]
        return Response(mock_data, status=status.HTTP_200_OK)

    def post(self, request):
        """노트 작성하기"""
        title = request.data.get("title", "제목 없음")
        content = request.data.get("content", "내용 없음")
        # 테스트 코드에서 title을 최상위 키로 기대함
        return Response(
            {"title": title, "content": content, "message": "노트 생성 성공 (테스트용)"},
            status=status.HTTP_201_CREATED,
        )


# 학습 단일조회/수정/삭제 (테스트용)
class StudyNoteRetrieveUpdateDestroyAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, note_id):
        """노트 상세조회"""
        dummy = {
            "id": note_id,
            "title": f"노트{note_id} 제목",
            "content": f"노트{note_id} 내용",
            "summary": "요약내용",
        }
        return Response(dummy, status=status.HTTP_200_OK)

    def patch(self, request, note_id):
        """노트 수정"""
        title = request.data.get("title", "수정제목")
        content = request.data.get("content", "수정내용")
        return Response({"id": note_id, "title": title, "content": content}, status=status.HTTP_200_OK)

    def delete(self, request, note_id):
        """노트 삭제"""
        return Response(status=status.HTTP_204_NO_CONTENT)


# 학습 요약조회 (테스트용)
class StudyNoteSummaryAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, note_id):
        """노트 요약보기"""
        dummy = {
            "id": note_id,
            "summary": f"노트{note_id} 요약입니다.",
            "created_at": timezone.now() - timedelta(days=1),
        }
        return Response(dummy, status=status.HTTP_200_OK)
