from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.recruitment_tag import RecruitmentTag
from apps.recruitments.serializers.recruitment_tag import RecruitmentTagSerializer


class RecruitmentTagListView(APIView):

    def get(self, request: Request, recruitment_id: int) -> Response:
        """특정 구인 공고에 연결된 모든 태그를 가져옵니다."""
        recruitment_tags = RecruitmentTag.objects.filter(recruitment_id=recruitment_id)

        # 태그가 없으면 404 오류 발생
        if not recruitment_tags:
            raise NotFound(detail="이 구인 공고에 연결된 태그가 없습니다.")

        # 직관적인 변수명을 사용하여 데이터를 직렬화하고 반환
        serializer = RecruitmentTagSerializer(recruitment_tags, many=True)
        return Response(serializer.data)

    def post(self, request: Request, recruitment_id: int) -> Response:
        """새로운 태그를 특정 구인 공고에 추가합니다."""
        # 요청 데이터에 구인 공고 ID 추가
        data = request.data.copy()
        data["recruitment"] = recruitment_id

        # 직렬화하여 유효성 검사 후 저장
        serializer = RecruitmentTagSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # 유효하지 않으면 오류 반환
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, recruitment_id: int, tag_id: int) -> Response:
        """특정 구인 공고에서 태그를 삭제합니다."""
        try:
            # 해당 태그를 찾고 삭제
            recruitment_tag = RecruitmentTag.objects.get(recruitment_id=recruitment_id, tag_id=tag_id)
        except RecruitmentTag.DoesNotExist:
            # 태그가 없으면 404 오류 발생
            raise NotFound(detail="해당 태그가 존재하지 않습니다.")

        # 태그 삭제 후 성공 메시지 반환
        recruitment_tag.delete()
        return Response({"detail": "태그가 성공적으로 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)
