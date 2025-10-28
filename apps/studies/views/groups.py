from typing import Any, Dict, List

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ...lecture.models import CrawledLecture
from ...users.models import User
from ..models.groups import GroupMember, StudyGroup, StudyLecture
from ..serializers.groups import (
    StudyGroupCreateSerializer,
    StudyGroupDetailSerializer,
    StudyGroupLectureSerializer,
    StudyGroupListSerializer,
    StudyGroupMemberSerializer,
)
from ..services.groups import StudyGroupService


class StudyGroupListCreateView(APIView):
    permission_classes = [AllowAny]

    # JSON, 이미지 파일을 요청으로부터 넘겨받기 위함
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    @extend_schema(
        operation_id="v1_studies_groups_create",
        tags=["StudyGroup"],
        summary="스터디 그룹 생성 API",
        request=StudyGroupCreateSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = StudyGroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="v1_studies_groups_list",
        tags=["StudyGroup"],
        summary="스터디 그룹 전체 목록 조회 API",
        responses={
            200: StudyGroupListSerializer(many=True),
        },
    )
    def get(self, request: Request) -> Response:
        mock_data: List[StudyGroup] = []

        for i in range(1, 11):
            start_at = f"2025-11-{str(i).zfill(2)}"
            end_at = f"2025-11-{str(i+20).zfill(2)}"
            group_status = StudyGroupService.get_status_by_date(start_at, end_at)

            study_group = StudyGroup(
                id=i,
                name=f"Mock Group {i}",
                # 결과가 불규칙한 2~10의 수로 나오는 수식
                max_headcount=(i * 7 % 9) + 2,
                profile_img_url=f"https://example.com/study{i}.png",
                start_at=start_at,
                end_at=end_at,
                status=group_status,
            )
            mock_data.append(study_group)

        # 실제 DB가 아니라 FK가 자동으로 연결되지 않으므로 따로 생성해서 데이터 추가
        lectures: list[CrawledLecture] = [
            CrawledLecture(
                id=i,
                title=f"example lecture{i}",
                instructor=f"example instructor{i}",
            )
            for i in range(1, 6)  # 1~5번 강의
        ]

        study_lectures: Dict[str, List[StudyLecture]] = {}
        for idx, study_group in enumerate(mock_data, start=1):
            # 결과가 불규칙한 1~5의 수로 나오는 수식
            lecture_count = ((idx * 3) % 5) + 1
            selected_lectures = lectures[:lecture_count]  # 앞에서 lecture_count개만 선택
            study_lectures[study_group.name] = [
                StudyLecture(study_group=study_group, lecture=lec) for lec in selected_lectures
            ]

        # Mock에서는 FK 참조 못해서 수동으로 응답 구성. 실 API에서는 시리얼라이저 사용.
        # 실 API에서 current_headcount 값은 prefetch로 참조(n+1 방지)
        serializer = StudyGroupListSerializer(mock_data, many=True)
        response_data = []

        for i, group in enumerate(mock_data, start=1):
            data = {
                "id": group.id,
                "name": group.name,
                "current_headcount": 2,
                "max_headcount": group.max_headcount,
                # 결과가 불규칙한 0~1의 수로 나오는 수식 + True, False로 변환
                "is_leader": ((i * 3 + 1) % 2) == 0,
                "profile_img_url": group.profile_img_url,
                "start_at": group.start_at,
                "end_at": group.end_at,
                "status": group.status,
                "lectures": StudyGroupLectureSerializer(study_lectures[group.name], many=True).data,
            }
            response_data.append(data)

        return Response(response_data, status=status.HTTP_200_OK)


class StudyGroupDetailUpdateView(APIView):
    permission_classes = [AllowAny]

    parser_classes = [parsers.JSONParser, parsers.MultiPartParser]

    def get_object(self) -> Dict[str, Any]:
        group_id = self.kwargs.get("group_id")
        if not group_id:
            raise ValidationError("group_id가 전달되지 않았습니다.")
        try:
            data_num = int(str(group_id)[-2:])
        except ValueError:
            raise ValidationError("테스트용입니다. UUID의 끝 2자리가 숫자가 아닙니다.")

        if data_num < 1 or data_num > 10:
            raise ValidationError("테스트용입니다. UUID의 끝 2자리를 1~10 사이의 숫자로 입력해주세요.")

        start_at = f"2025-11-{str(data_num).zfill(2)}"
        end_at = f"2025-11-{str(data_num+20).zfill(2)}"
        group_status = StudyGroupService.get_status_by_date(start_at, end_at)

        mock_data = StudyGroup(
            id=data_num,
            name=f"Mock Group {data_num}",
            # 결과가 불규칙한 2~10의 수로 나오는 수식
            max_headcount=(data_num * 7 % 9) + 2,
            profile_img_url=f"https://example.com/study{data_num}.png",
            start_at=start_at,
            end_at=end_at,
            status=group_status,
        )

        # 실제 DB가 아니라 FK가 자동으로 연결되지 않으므로 따로 생성해서 데이터 추가
        lectures: list[CrawledLecture] = [
            CrawledLecture(
                id=i,
                thumbnail_img_url=f"https://example.com/lecture{i}.png",
                title=f"example lecture{i}",
                instructor=f"example instructor{i}",
                url_link=f"https://example.com/lecture{i}",
            )
            for i in range(1, 6)  # 1~5번 강의
        ]

        study_lectures: Dict[str, List[StudyLecture]] = {}
        # 결과가 불규칙한 1~5의 수로 나오는 수식
        lecture_count = ((data_num * 3) % 5) + 1
        selected_lectures = lectures[:lecture_count]  # 앞에서 lecture_count개만 선택
        study_lectures[mock_data.name] = [StudyLecture(study_group=mock_data, lecture=lec) for lec in selected_lectures]

        users = [User(nickname=f"nickname{data_num}"), User(nickname=f"nickname{data_num + 1}")]

        members = [
            GroupMember(user=users[0], is_leader=True),
            GroupMember(user=users[1], is_leader=False),
        ]

        group_members: Dict[str, List[GroupMember]] = {}
        member_count = 2
        selected_members = members[:member_count]
        group_members[mock_data.name] = [
            GroupMember(study_group=mock_data, user=member.user, is_leader=member.is_leader)
            for member in selected_members
        ]

        # Mock에서는 FK 참조 못해서 수동으로 응답 구성. 실 API에서는 시리얼라이저 사용.
        # serializer = StudyGroupDetailSerializer(mock_data)

        response_data = {
            "id": data_num,
            "name": mock_data.name,
            "current_headcount": 2,
            "max_headcount": mock_data.max_headcount,
            "members": StudyGroupMemberSerializer(group_members[mock_data.name], many=True).data,
            "profile_img_url": mock_data.profile_img_url,
            "start_at": mock_data.start_at,
            "end_at": mock_data.end_at,
            "status": mock_data.status,
            "lectures": StudyGroupLectureSerializer(study_lectures[mock_data.name], many=True).data,
        }

        return response_data

    @extend_schema(
        operation_id="v1_studies_groups_detail",
        tags=["StudyGroup"],
        summary="스터디 그룹 상세 조회 API",
        description=(
            """
            현재 API는 Spec API이므로
            00000000-0000-0000-0000-000000000001 에서
            00000000-0000-0000-0000-000000000010 까지의
            값으로 테스트해주세요.
            """
        ),
        responses={
            200: StudyGroupDetailSerializer(many=True),
        },
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response_data = self.get_object()
        return Response(response_data, status=status.HTTP_200_OK)
