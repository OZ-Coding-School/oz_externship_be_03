from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.recruitment_tag import RecruitmentTag
from apps.recruitments.serializers.recruitment_tag import RecruitmentTagSerializer


class RecruitmentTagListView(APIView):
    def get(self, request: Request, recruitment_id: int) -> Response:
        recruitment_tags = RecruitmentTag.objects.filter(recruitment_id=recruitment_id)
        if not recruitment_tags.exists():
            raise NotFound(detail="No tags found for this recruitment.")

        serializer: RecruitmentTagSerializer = RecruitmentTagSerializer(recruitment_tags, many=True)
        return Response(serializer.data)

    def post(self, request: Request, recruitment_id: int) -> Response:
        data = request.data.copy()
        data["recruitment"] = recruitment_id

        serializer: RecruitmentTagSerializer = RecruitmentTagSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, recruitment_id: int, tag_id: int) -> Response:
        try:
            recruitment_tag = RecruitmentTag.objects.get(recruitment_id=recruitment_id, tag_id=tag_id)
        except RecruitmentTag.DoesNotExist:
            raise NotFound(detail="Recruitment tag not found.")

        recruitment_tag.delete()
        return Response({"detail": "Tag deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
