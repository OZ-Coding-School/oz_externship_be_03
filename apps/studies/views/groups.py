from datetime import date
from typing import Any

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from ..serializers.groups import StudyGroupCreateSerializer


# 스터디 그룹 생성
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 생성",
    description="로그인 사용자가 스터디 그룹을 생성합니다. 선택 필드 포함.",
    request=StudyGroupCreateSerializer,
    responses={
        201: OpenApiExample(
            name="성공 예시",
            value={
                "id": 101,
                "name": "AI 웹서비스 스터디",
                "introduction": "AI 웹서비스를 함께 공부하는 스터디입니다.",
                "profile_img_url": "https://example.com/study101.png",
                "start_at": "2025-11-01",
                "end_at": "2025-11-25",
                "max_members": 6,
                "status": "PENDING",
                "lectures": [
                    {"id": 1, "title": "Python 심화", "instructor": "송상헌"},
                    {"id": 2, "title": "Django 입문", "instructor": "안현기"},
                ],
                "leader": {"id": 5, "name": "정다몬"},
                "message": "스터디 그룹이 성공적으로 생성되었습니다.",
            },
            response_only=True,
        ),
        400: OpenApiExample(
            name="유효성 실패 예시",
            value={
                "error_code": "ERROR400",
                "message": "유효하지 않은 입력입니다.",
                "detail": "종료일은 시작일보다 최소 5일 이후여야 합니다.",
            },
            response_only=True,
        ),
        403: OpenApiExample(
            name="권한 실패 예시",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "로그인 후 이용 가능합니다.",
            },
            response_only=True,
        ),
    },
)
class StudyGroupCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = {
            "id": 101,
            "name": "AI 웹서비스 스터디",
            "introduction": "AI 웹서비스를 함께 공부하는 스터디입니다.",
            "profile_img_url": "https://example.com/study101.png",
            "start_at": "2025-11-01",
            "end_at": "2025-11-25",
            "max_members": 6,
            "status": "PENDING",
            "lectures": [
                {"id": 1, "title": "Python 심화", "instructor": "이혁"},
                {"id": 2, "title": "Django 입문", "instructor": "이형운"},
            ],
            "leader": {"id": 5, "name": "송상헌"},
            "message": "스터디 그룹이 성공적으로 생성되었습니다.",
        }
        return Response(data, status=201)


# 시작일 및 종료일 선택
@extend_schema(
    tags=["스터디 그룹"],
    summary="스터디 그룹 시작일·종료일 선택 제약 (스펙용)",
    description=(
        "스터디 그룹 생성 시 프론트의 캘린더 UI에서 선택 가능한 날짜 범위를 제공합니다.\n\n"
        "- 시작일은 오늘 또는 오늘 이후만 가능\n"
        "- 종료일은 시작일로부터 최소 5일 이후만 가능"
    ),
    responses={
        200: OpenApiExample(
            name="예시 응답",
            value={
                "today": "2025-10-16",
                "min_start_date": "2025-10-16",
                "min_end_date_offset_days": 5,
                "example_rule": "종료일은 선택된 시작일로부터 최소 5일 이후여야 합니다.",
            },
            response_only=True,
        ),
    },
)
class StudyGroupDateConstraintView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        today = date.today()
        data = {
            "today": today.isoformat(),
            "min_start_date": today.isoformat(),
            "min_end_date_offset_days": 5,
            "example_rule": "종료일은 선택된 시작일로부터 최소 5일 이후여야 합니다.",
        }
        return Response(data)


# 스터디 그룹 목록 조회
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 목록 조회",
    description="사용자가 속한 모든 스터디 그룹 목록을 조회합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "groups": [
                    {
                        "id": 101,
                        "name": "AI 웹서비스 스터디",
                        "profile_img_url": "https://example.com/study101.png",
                        "current_members": 5,
                        "max_members": 6,
                        "is_leader": True,
                        "start_at": "2025-11-01",
                        "end_at": "2025-11-25",
                        "status": "ONGOING",
                        "lectures": [
                            {"title": "Python 심화", "instructor": "이형운"},
                            {"title": "Django 입문", "instructor": "이혁"},
                        ],
                    }
                ]
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="데이터 없음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "가입된 스터디 그룹이 없습니다.",
            },
            response_only=True,
        ),
    },
)
class StudyGroupListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = {
            "groups": [
                {
                    "id": 101,
                    "name": "AI 웹서비스 스터디",
                    "profile_img_url": "https://example.com/study101.png",
                    "current_members": 5,
                    "max_members": 6,
                    "is_leader": True,
                    "start_at": "2025-11-01",
                    "end_at": "2025-11-25",
                    "status": "ONGOING",
                    "lectures": [
                        {"title": "Python 심화", "instructor": "안현기"},
                        {"title": "Django 입문", "instructor": "정다몬"},
                    ],
                }
            ]
        }
        return Response(data)


# 스터디 그룹 상세 조회
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 상세 조회",
    description="스터디 그룹의 상세 정보를 조회합니다. (멤버/강의 포함)",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "id": 101,
                "name": "AI 웹서비스 스터디",
                "introduction": "AI 웹서비스를 함께 공부하는 스터디입니다.",
                "profile_img_url": "https://example.com/study101.png",
                "start_at": "2025-11-01",
                "end_at": "2025-11-25",
                "max_members": 6,
                "status": "ONGOING",
                "leader": {"id": 1, "name": "이형운"},
                "members": [
                    {"id": 1, "name": "이형운", "is_leader": True},
                    {"id": 2, "name": "정다몬", "is_leader": False},
                    {"id": 3, "name": "송상헌", "is_leader": False},
                    {"id": 4, "name": "안현기", "is_leader": False},
                    {"id": 5, "name": "이혁", "is_leader": False},
                ],
                "lectures": [
                    {
                        "id": 1,
                        "title": "Django REST Framework 마스터하기",
                        "instructor": "정다몬",
                        "thumbnail_url": "https://example.com/lectures/drf.png",
                        "link": "https://ozcoding.com/lectures/1",
                    },
                    {
                        "id": 2,
                        "title": "AWS 인프라 기초",
                        "instructor": "이혁",
                        "thumbnail_url": "https://example.com/lectures/aws.png",
                        "link": "https://ozcoding.com/lectures/2",
                    },
                ],
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="리소스 없음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 스터디 그룹이 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class StudyGroupDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "id": group_id,
            "name": "AI 웹서비스 스터디",
            "introduction": "AI 웹서비스를 함께 공부하는 스터디입니다.",
            "profile_img_url": "https://example.com/study101.png",
            "start_at": "2025-11-01",
            "end_at": "2025-11-25",
            "max_members": 6,
            "status": "ONGOING",
            "leader": {"id": 1, "name": "이형운"},
            "members": [
                {"id": 1, "name": "이형운", "is_leader": True},
                {"id": 2, "name": "정다몬", "is_leader": False},
                {"id": 3, "name": "송상헌", "is_leader": False},
                {"id": 4, "name": "안현기", "is_leader": False},
                {"id": 5, "name": "이혁", "is_leader": False},
            ],
            "lectures": [
                {
                    "id": 1,
                    "title": "Django REST Framework 마스터하기",
                    "instructor": "정다몬",
                    "thumbnail_url": "https://example.com/lectures/drf.png",
                    "link": "https://ozcoding.com/lectures/1",
                },
                {
                    "id": 2,
                    "title": "AWS 인프라 기초",
                    "instructor": "이혁",
                    "thumbnail_url": "https://example.com/lectures/aws.png",
                    "link": "https://ozcoding.com/lectures/2",
                },
            ],
        }
        return Response(data)


# 스터디 그룹 정보 수정
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 정보 수정",
    description="스터디 리더만 스터디 그룹 정보를 수정할 수 있습니다.",
    request=StudyGroupCreateSerializer,
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "id": 101,
                "name": "AI 프로젝트 심화 스터디",
                "introduction": "AI 기반 웹서비스를 심도 있게 다루는 그룹입니다.",
                "profile_img_url": "https://example.com/study101_v2.png",
                "start_at": "2025-11-05",
                "end_at": "2025-11-30",
                "max_members": 8,
                "status": "PENDING",
                "leader": {"id": 1, "name": "이형운"},
                "message": "스터디 그룹 정보가 성공적으로 수정되었습니다.",
            },
            response_only=True,
        ),
        403: OpenApiExample(
            name="권한 없음",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "스터디 리더만 수정할 수 있습니다.",
            },
            response_only=True,
        ),
        400: OpenApiExample(
            name="유효성 실패",
            value={
                "error_code": "ERROR400",
                "message": "유효하지 않은 입력입니다.",
                "detail": "종료일은 시작일보다 최소 5일 이후여야 합니다.",
            },
            response_only=True,
        ),
    },
)
class StudyGroupUpdateView(APIView):
    permission_classes = [AllowAny]

    def put(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "id": group_id,
            "name": "AI 프로젝트 심화 스터디",
            "introduction": "AI 기반 웹서비스를 심도 있게 다루는 그룹입니다.",
            "profile_img_url": "https://example.com/study101_v2.png",
            "start_at": "2025-11-05",
            "end_at": "2025-11-30",
            "max_members": 8,
            "status": "PENDING",
            "leader": {"id": 1, "name": "이형운"},
            "message": "스터디 그룹 정보가 성공적으로 수정되었습니다.",
        }
        return Response(data)


# 스터디 그룹 삭제
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 삭제",
    description="스터디 리더만 그룹을 삭제할 수 있습니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={"message": "스터디 그룹이 성공적으로 삭제되었습니다."},
            response_only=True,
        ),
        403: OpenApiExample(
            name="권한 없음",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "스터디 리더만 그룹을 삭제할 수 있습니다.",
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="존재하지 않음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 스터디 그룹이 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class StudyGroupDeleteView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        return Response({"message": "스터디 그룹이 성공적으로 삭제되었습니다."})


# 스터디 멤버 추방
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 멤버 추방",
    description="스터디 리더가 특정 멤버를 그룹에서 추방합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "message": "멤버가 스터디 그룹에서 추방되었습니다.",
                "kicked_member": {"id": 4, "name": "안현기"},
                "remaining_members": [
                    {"id": 1, "name": "이형운", "is_leader": True},
                    {"id": 2, "name": "정다몬", "is_leader": False},
                    {"id": 3, "name": "송상헌", "is_leader": False},
                    {"id": 5, "name": "이혁", "is_leader": False},
                ],
            },
            response_only=True,
        ),
        403: OpenApiExample(
            name="권한 없음",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "스터디 리더만 멤버를 추방할 수 있습니다.",
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="존재하지 않음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 멤버가 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class StudyMemberKickView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request: Request, group_id: int, member_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "message": "멤버가 스터디 그룹에서 추방되었습니다.",
            "kicked_member": {"id": member_id, "name": "안현기"},
            "remaining_members": [
                {"id": 1, "name": "이형운", "is_leader": True},
                {"id": 2, "name": "정다몬", "is_leader": False},
                {"id": 3, "name": "송상헌", "is_leader": False},
                {"id": 5, "name": "이혁", "is_leader": False},
            ],
        }
        return Response(data)


# 스터디 그룹 나가기
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 나가기",
    description="스터디 멤버가 직접 스터디 그룹을 나갑니다. 리더의 경우 위임 후 탈퇴해야 합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "message": "스터디 그룹에서 성공적으로 나갔습니다.",
                "left_member": {"id": 3, "name": "송상헌"},
            },
            response_only=True,
        ),
        403: OpenApiExample(
            name="리더 탈퇴 제한",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "리더는 탈퇴 전에 리더 권한을 위임해야 합니다.",
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="그룹 없음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 스터디 그룹이 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class StudyMemberLeaveView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "message": "스터디 그룹에서 성공적으로 나갔습니다.",
            "left_member": {"id": 3, "name": "송상헌"},
        }
        return Response(data)


# 스터디 리더 위임
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 리더 위임",
    description="현재 리더가 특정 멤버에게 리더 권한을 위임합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "message": "리더 권한이 성공적으로 위임되었습니다.",
                "previous_leader": {"id": 1, "name": "이형운"},
                "new_leader": {"id": 2, "name": "정다몬"},
                "members": [
                    {"id": 1, "name": "이형운", "is_leader": False},
                    {"id": 2, "name": "정다몬", "is_leader": True},
                    {"id": 3, "name": "송상헌", "is_leader": False},
                    {"id": 4, "name": "안현기", "is_leader": False},
                    {"id": 5, "name": "이혁", "is_leader": False},
                ],
            },
            response_only=True,
        ),
        403: OpenApiExample(
            name="권한 없음",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "스터디 리더만 위임할 수 있습니다.",
            },
            response_only=True,
        ),
        400: OpenApiExample(
            name="잘못된 대상",
            value={
                "error_code": "ERROR400",
                "message": "유효하지 않은 요청입니다.",
                "detail": "리더 권한은 본인에게 위임할 수 없습니다.",
            },
            response_only=True,
        ),
    },
)
class StudyMemberDelegateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, group_id: int, member_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "message": "리더 권한이 성공적으로 위임되었습니다.",
            "previous_leader": {"id": 1, "name": "이형운"},
            "new_leader": {"id": member_id, "name": "정다몬"},
            "members": [
                {"id": 1, "name": "이형운", "is_leader": False},
                {"id": 2, "name": "정다몬", "is_leader": True},
                {"id": 3, "name": "송상헌", "is_leader": False},
                {"id": 4, "name": "안현기", "is_leader": False},
                {"id": 5, "name": "이혁", "is_leader": False},
            ],
        }
        return Response(data)


# 스터디 그룹 강의 목록 조회
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 강의 목록 조회",
    description="특정 스터디 그룹에서 수강 중인 강의 목록을 조회합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "study_group_id": 101,
                "study_group_name": "AI 웹서비스 스터디",
                "lectures": [
                    {
                        "lecture_id": 1,
                        "title": "Python 고급 문법 마스터",
                        "instructor": "정다몬",
                        "duration": "12시간",
                        "thumbnail_url": "https://example.com/lectures/python.png",
                        "link": "https://ozcoding.com/lectures/1",
                        "created_at": "2025-10-15T10:00:00",
                    },
                    {
                        "lecture_id": 2,
                        "title": "Django 심화와 배포",
                        "instructor": "이혁",
                        "duration": "15시간",
                        "thumbnail_url": "https://example.com/lectures/django.png",
                        "link": "https://ozcoding.com/lectures/2",
                        "created_at": "2025-10-16T09:30:00",
                    },
                    {
                        "lecture_id": 3,
                        "title": "AWS 서비스 이해",
                        "instructor": "송상헌",
                        "duration": "10시간",
                        "thumbnail_url": "https://example.com/lectures/aws.png",
                        "link": "https://ozcoding.com/lectures/3",
                        "created_at": "2025-10-17T11:15:00",
                    },
                ],
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="리소스 없음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 스터디 그룹이 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class StudyLectureListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        query = request.query_params.get("q", "").strip()
        limit = int(request.query_params.get("limit", 5))
        offset = int(request.query_params.get("offset", 0))

        lectures = [
            {
                "lecture_id": 1,
                "title": "Python 고급 문법 마스터",
                "instructor": "정다몬",
                "duration": "12시간",
                "thumbnail_url": "https://example.com/lectures/python.png",
                "link": "https://ozcoding.com/lectures/1",
                "created_at": "2025-10-15T10:00:00",
            },
            {
                "lecture_id": 2,
                "title": "Django 심화와 배포",
                "instructor": "이혁",
                "duration": "15시간",
                "thumbnail_url": "https://example.com/lectures/django.png",
                "link": "https://ozcoding.com/lectures/2",
                "created_at": "2025-10-16T09:30:00",
            },
            {
                "lecture_id": 3,
                "title": "AWS 서비스 이해",
                "instructor": "송상헌",
                "duration": "10시간",
                "thumbnail_url": "https://example.com/lectures/aws.png",
                "link": "https://ozcoding.com/lectures/3",
                "created_at": "2025-10-17T11:15:00",
            },
        ]

        # 검색 (부분 일치: 강의명 / 강사명)
        query_param = request.query_params.get("query", "")
        query_str: str = str(query_param).strip()

        if query_str:
            query_lower = query_str.lower()
            lectures = [
                l
                for l in lectures
                if query_lower in str(l["title"]).lower() or query_lower in str(l["instructor"]).lower()
            ]

        # 페이지네이션 (limit-offset)
        total = len(lectures)
        paginated = lectures[offset : offset + limit]

        data = {
            "study_group_id": group_id,
            "study_group_name": "AI 웹서비스 스터디",
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": paginated,
        }

        return Response(data)


# 스터디 그룹 일정 목록 조회
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 일정 목록 조회",
    description="특정 스터디 그룹의 전체 스케줄을 조회합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "study_group_id": 101,
                "study_group_name": "AI 웹서비스 스터디",
                "schedules": [
                    {
                        "id": 1,
                        "title": "1회차 - OT 및 목표 설정",
                        "objective": "스터디 목표와 학습 주제 공유",
                        "session_date": "2025-11-01",
                        "start_time": "19:00",
                        "end_time": "21:00",
                        "participants": [
                            {"id": 1, "name": "이형운"},
                            {"id": 2, "name": "정다몬"},
                            {"id": 3, "name": "송상헌"},
                        ],
                    },
                    {
                        "id": 2,
                        "title": "2회차 - Django ORM 실습",
                        "objective": "모델 설계 및 쿼리 실습",
                        "session_date": "2025-11-08",
                        "start_time": "19:00",
                        "end_time": "21:00",
                        "participants": [
                            {"id": 1, "name": "이형운"},
                            {"id": 4, "name": "안현기"},
                            {"id": 5, "name": "이혁"},
                        ],
                    },
                ],
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="리소스 없음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 스터디 그룹이 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class GroupScheduleListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "study_group_id": group_id,
            "study_group_name": "AI 웹서비스 스터디",
            "schedules": [
                {
                    "id": 1,
                    "title": "1회차 - OT 및 목표 설정",
                    "objective": "스터디 목표와 학습 주제 공유",
                    "session_date": "2025-11-01",
                    "start_time": "19:00",
                    "end_time": "21:00",
                    "participants": [
                        {"id": 1, "name": "이형운"},
                        {"id": 2, "name": "정다몬"},
                        {"id": 3, "name": "송상헌"},
                    ],
                },
                {
                    "id": 2,
                    "title": "2회차 - Django ORM 실습",
                    "objective": "모델 설계 및 쿼리 실습",
                    "session_date": "2025-11-08",
                    "start_time": "19:00",
                    "end_time": "21:00",
                    "participants": [
                        {"id": 1, "name": "이형운"},
                        {"id": 4, "name": "안현기"},
                        {"id": 5, "name": "이혁"},
                    ],
                },
            ],
        }
        return Response(data)


# 스터디 그룹 일정 생성
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 그룹 일정 생성",
    description="스터디 리더가 새로운 스케줄을 등록합니다.",
    request=OpenApiExample(
        name="요청 예시",
        value={
            "title": "3회차 - 배포 자동화",
            "objective": "GitHub Actions로 CI/CD 구성 실습",
            "session_date": "2025-11-15",
            "start_time": "19:00",
            "end_time": "21:00",
        },
    ),
    responses={
        201: OpenApiExample(
            name="성공 예시",
            value={
                "message": "스터디 일정이 성공적으로 등록되었습니다.",
                "schedule": {
                    "id": 3,
                    "title": "3회차 - 배포 자동화",
                    "objective": "GitHub Actions로 CI/CD 구성 실습",
                    "session_date": "2025-11-15",
                    "start_time": "19:00",
                    "end_time": "21:00",
                },
            },
            response_only=True,
        ),
        400: OpenApiExample(
            name="유효성 실패",
            value={
                "error_code": "ERROR400",
                "message": "유효하지 않은 요청입니다.",
                "detail": "종료 시간이 시작 시간보다 빠릅니다.",
            },
            response_only=True,
        ),
        403: OpenApiExample(
            name="권한 없음",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "스터디 리더만 일정을 생성할 수 있습니다.",
            },
            response_only=True,
        ),
    },
)
class GroupScheduleCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "message": "스터디 일정이 성공적으로 등록되었습니다.",
            "schedule": {
                "id": 3,
                "title": "3회차 - 배포 자동화",
                "objective": "GitHub Actions로 CI/CD 구성 실습",
                "session_date": "2025-11-15",
                "start_time": "19:00",
                "end_time": "21:00",
            },
        }
        return Response(data, status=201)


# 스터디 스케줄 참여
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 일정 참여",
    description="멤버가 특정 스케줄에 참여 신청을 합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "message": "스터디 일정에 참여가 완료되었습니다.",
                "schedule_id": 1,
                "participant": {"id": 4, "name": "안현기"},
            },
            response_only=True,
        ),
        409: OpenApiExample(
            name="중복 참여",
            value={
                "error_code": "ERROR409",
                "message": "중복 요청입니다.",
                "detail": "이미 해당 일정에 참여 중입니다.",
            },
            response_only=True,
        ),
    },
)
class GroupScheduleJoinView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, schedule_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "message": "스터디 일정에 참여가 완료되었습니다.",
            "schedule_id": schedule_id,
            "participant": {"id": 4, "name": "안현기"},
        }
        return Response(data)


# 스터디 스케줄 참여 취소
@extend_schema(
    tags=["Studygroup"],
    summary="스터디 일정 참여 취소",
    description="참여 중인 멤버가 스케줄 참여를 취소합니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "message": "스터디 일정 참여가 취소되었습니다.",
                "schedule_id": 1,
                "participant": {"id": 4, "name": "안현기"},
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="참여자 없음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 참여자가 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class GroupScheduleLeaveView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request: Request, schedule_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "message": "스터디 일정 참여가 취소되었습니다.",
            "schedule_id": schedule_id,
            "participant": {"id": 4, "name": "안현기"},
        }
        return Response(data)


# 스터디 그룹상태 수정
@extend_schema(
    tags=["스터디 그룹"],
    summary="스터디 상태 자동 업데이트 (스펙용)",
    description=(
        "매일 00:01 (KST 기준) 종료일이 오늘 이전인 스터디 그룹의 상태를 "
        "'종료됨'으로 일괄 변경하는 예약 작업입니다.\n\n"
        "현재는 실제 Celery 연동이 아닌 **스펙 전용 Mock 응답**을 반환합니다."
    ),
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "task": "update_study_status",
                "description": "매일 00:01 (KST 기준) 종료일이 오늘 이전인 스터디 그룹을 '종료됨' 상태로 일괄 변경합니다.",
                "example_result": {
                    "updated_groups": 3,
                    "updated_ids": [101, 105, 110],
                    "updated_at": "2025-10-16T00:01:00+09:00",
                },
                "status": "스펙 전용 Mock 응답 (실제 Celery 연동 시 자동화 예정)",
            },
            response_only=True,
        ),
    },
)
class StudyGroupStatusAutoUpdateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = {
            "task": "update_study_status",
            "description": "매일 00:01 (KST 기준) 종료일이 오늘 이전인 스터디 그룹을 '종료됨' 상태로 일괄 변경합니다.",
            "example_result": {
                "updated_groups": 3,
                "updated_ids": [101, 105, 110],
                "updated_at": "2025-10-16T00:01:00+09:00",
            },
            "status": "스펙 전용 Mock 응답 (실제 Celery 연동 시 자동화 예정)",
        }
        return Response(data)


# 관리자 전용 스터디 그룹 목록 조회
@extend_schema(
    tags=["Studygroup"],
    summary="관리자용 스터디 그룹 목록 조회",
    description="관리자는 생성된 모든 스터디 그룹을 상태별로 조회할 수 있습니다.",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "count": 3,
                "results": [
                    {
                        "id": 1,
                        "uuid": "c31d3e84-12aa-47e7-98b1-9f4a9c10b1cc",
                        "name": "AI 웹서비스 스터디",
                        "status": "ONGOING",
                        "max_headcount": 6,
                        "current_members": 5,
                        "start_at": "2025-11-01",
                        "end_at": "2025-11-25",
                        "leader_name": "이형운",
                        "created_at": "2025-10-05T14:30:00Z",
                        "updated_at": "2025-10-10T12:10:00Z",
                    },
                    {
                        "id": 2,
                        "uuid": "6a4b8f31-b1c5-487a-a6b7-0a48277dbf91",
                        "name": "딥러닝 모델링 스터디",
                        "status": "PENDING",
                        "max_headcount": 8,
                        "current_members": 3,
                        "start_at": "2025-12-01",
                        "end_at": "2026-01-15",
                        "leader_name": "정다몬",
                        "created_at": "2025-10-11T09:00:00Z",
                        "updated_at": "2025-10-13T10:40:00Z",
                    },
                ],
            },
            response_only=True,
        ),
        403: OpenApiExample(
            name="권한 없음",
            value={
                "error_code": "ERROR403",
                "message": "권한이 없습니다.",
                "detail": "관리자만 접근할 수 있는 API입니다.",
            },
            response_only=True,
        ),
    },
)
class AdminStudyGroupListView(APIView):
    # 관리자만 접근 가능
    permission_classes = [IsAdminUser]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = {
            "count": 3,
            "results": [
                {
                    "id": 1,
                    "uuid": "c31d3e84-12aa-47e7-98b1-9f4a9c10b1cc",
                    "name": "AI 웹서비스 스터디",
                    "status": "ONGOING",
                    "max_headcount": 6,
                    "current_members": 5,
                    "start_at": "2025-11-01",
                    "end_at": "2025-11-25",
                    "leader_name": "이형운",
                    "created_at": "2025-10-05T14:30:00Z",
                    "updated_at": "2025-10-10T12:10:00Z",
                },
                {
                    "id": 2,
                    "uuid": "6a4b8f31-b1c5-487a-a6b7-0a48277dbf91",
                    "name": "딥러닝 모델링 스터디",
                    "status": "PENDING",
                    "max_headcount": 8,
                    "current_members": 3,
                    "start_at": "2025-12-01",
                    "end_at": "2026-01-15",
                    "leader_name": "정다몬",
                    "created_at": "2025-10-11T09:00:00Z",
                    "updated_at": "2025-10-13T10:40:00Z",
                },
            ],
        }
        return Response(data)


# 관리자 전용 스터디 그룹 상세 조회
@extend_schema(
    tags=["Studygroup"],
    summary="관리자용 스터디 그룹 상세 조회",
    description="관리자는 특정 스터디 그룹의 상세 정보를 조회할 수 있습니다. (멤버 / 강의 포함)",
    responses={
        200: OpenApiExample(
            name="성공 예시",
            value={
                "id": 1,
                "uuid": "c31d3e84-12aa-47e7-98b1-9f4a9c10b1cc",
                "name": "AI 웹서비스 스터디",
                "introduction": "AI 웹서비스 개발을 목표로 한 팀 스터디입니다.",
                "profile_img_url": "https://example.com/study101.png",
                "status": "ONGOING",
                "max_headcount": 6,
                "current_members": 5,
                "start_at": "2025-11-01",
                "end_at": "2025-11-25",
                "leader": {"id": 1, "name": "이형운"},
                "members": [
                    {"id": 1, "name": "이형운", "is_leader": True},
                    {"id": 2, "name": "정다몬", "is_leader": False},
                    {"id": 3, "name": "송상헌", "is_leader": False},
                    {"id": 4, "name": "안현기", "is_leader": False},
                    {"id": 5, "name": "이혁", "is_leader": False},
                ],
                "lectures": [
                    {"id": 10, "title": "Python 심화", "instructor": "홍길동"},
                    {"id": 11, "title": "Django ORM 실습", "instructor": "이몽룡"},
                ],
                "created_at": "2025-10-05T14:30:00Z",
                "updated_at": "2025-10-10T12:10:00Z",
            },
            response_only=True,
        ),
        404: OpenApiExample(
            name="리소스 없음",
            value={
                "error_code": "ERROR404",
                "message": "리소스를 찾을 수 없습니다.",
                "detail": "해당 스터디 그룹이 존재하지 않습니다.",
            },
            response_only=True,
        ),
    },
)
class AdminStudyGroupDetailView(APIView):
    # 관리자만 접근 가능
    permission_classes = [IsAdminUser]

    def get(self, request: Request, studygroup_id: int, *args: Any, **kwargs: Any) -> Response:
        data = {
            "id": studygroup_id,
            "uuid": "c31d3e84-12aa-47e7-98b1-9f4a9c10b1cc",
            "name": "AI 웹서비스 스터디",
            "introduction": "AI 웹서비스 개발을 목표로 한 팀 스터디입니다.",
            "profile_img_url": "https://example.com/study101.png",
            "status": "ONGOING",
            "max_headcount": 6,
            "current_members": 5,
            "start_at": "2025-11-01",
            "end_at": "2025-11-25",
            "leader": {"id": 1, "name": "이형운"},
            "members": [
                {"id": 1, "name": "이형운", "is_leader": True},
                {"id": 2, "name": "정다몬", "is_leader": False},
                {"id": 3, "name": "송상헌", "is_leader": False},
                {"id": 4, "name": "안현기", "is_leader": False},
                {"id": 5, "name": "이혁", "is_leader": False},
            ],
            "lectures": [
                {"id": 10, "title": "Python 심화", "instructor": "홍길동"},
                {"id": 11, "title": "Django ORM 실습", "instructor": "이몽룡"},
            ],
            "created_at": "2025-10-05T14:30:00Z",
            "updated_at": "2025-10-10T12:10:00Z",
        }
        return Response(data)
