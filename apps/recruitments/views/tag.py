from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.tag import Tag  # Tag 모델 임포트
from apps.recruitments.serializers.tag import TagSerializer


class TagListView(APIView):
    def get(self, request: Request) -> Response:
        """전체 태그 목록을 반환합니다."""
        # 실제 DB에서 Tag 객체를 조회합니다.
        tags = Tag.objects.all()  # 실제 데이터베이스에서 모든 태그를 가져옵니다.

        # 태그 데이터를 직렬화하고 유효성을 검사합니다.
        serializer = TagSerializer(tags, many=True)  # 실제 Tag 객체를 전달
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        """새로운 태그를 추가합니다."""
        new_tag_name = request.data.get("name")

        # 태그 이름이 없으면 오류 메시지 반환
        if not new_tag_name:
            return Response({"error": "태그 이름은 필수 항목입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 새로운 태그를 생성하고 저장합니다.
        new_tag = Tag.objects.create(name=new_tag_name)

        # 새로 생성된 태그를 직렬화하고 반환합니다.
        serializer = TagSerializer(new_tag)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    def get(self, request: Request, tag_id: int) -> Response:
        """특정 태그를 조회합니다."""
        try:
            tag = Tag.objects.get(id=tag_id)  # 실제 DB에서 해당 ID로 태그를 조회
        except Tag.DoesNotExist:
            raise NotFound(detail="태그를 찾을 수 없습니다.")

        # 태그를 직렬화하고 반환합니다.
        serializer = TagSerializer(tag)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data)

    def put(self, request: Request, tag_id: int) -> Response:
        """특정 태그를 수정합니다."""
        tag_name = request.data.get("name")

        if not tag_name:
            return Response({"error": "태그 이름은 필수 항목입니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tag = Tag.objects.get(id=tag_id)  # 수정할 태그를 조회
            tag.name = tag_name  # 태그 이름을 수정
            tag.save()  # 수정 사항 저장
        except Tag.DoesNotExist:
            raise NotFound(detail="태그를 찾을 수 없습니다.")

        # 수정된 태그를 직렬화하고 반환합니다.
        serializer = TagSerializer(tag)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data)

    def delete(self, request: Request, tag_id: int) -> Response:
        """특정 태그를 삭제합니다."""
        try:
            tag = Tag.objects.get(id=tag_id)  # 삭제할 태그를 조회
            tag.delete()  # 태그 삭제
        except Tag.DoesNotExist:
            raise NotFound(detail="태그를 찾을 수 없습니다.")

        return Response(
            {"detail": f"태그 {tag_id}가 성공적으로 삭제되었습니다."},
            status=status.HTTP_204_NO_CONTENT,
        )
