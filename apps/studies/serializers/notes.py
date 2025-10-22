from rest_framework import serializers

from apps.studies.models.notes import StudyNote


# 노트 작성용 Serializer
class StudyNoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyNote
        fields = ["title", "content"]
