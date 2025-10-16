from rest_framework import serializers
from .models import StudyNote


class AuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nickname = serializers.CharField(read_only=True)

#작성자정보는 위에서 만든 AuthorSerializer로 가져오게 작성했습니다 
class StudyNoteSerializer(serializers.ModelSerializer):
    #불필요한 개인정보가 유출될수있어서 필요한정보만 빠지게 작성
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = StudyNote
        fields = [
            "id",
            "group",
            "author",
            "title",
            "content",
            "summary",
            "created_at",
            "updated_at",
        ]
        #직접못바꾸는 항목들입니다
        read_only_fields = ["id", "author", "summary", "created_at", "updated_at"]

#노트를 새로 작성할 때만 사용하는 시리얼라이저
class StudyNoteCreateSerializer(serializers.ModelSerializer):
    """POST 요청용 Serializer"""

    class Meta:
        model = StudyNote
        fields = ["title", "content"]
