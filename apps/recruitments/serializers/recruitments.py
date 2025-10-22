from rest_framework import serializers

from apps.recruitments.models.recruitments import Recruitment


class RecruitmentSerializer(serializers.ModelSerializer[Recruitment]):
    id = serializers.IntegerField(read_only=True)
    uuid = serializers.UUIDField(read_only=True)
    title = serializers.CharField(max_length=50)
    content = serializers.CharField()
    estimated_fee = serializers.IntegerField()
    expected_headcount = serializers.IntegerField()
    views_count = serializers.IntegerField(default=0)
    close_at = serializers.DateTimeField()
    is_closed = serializers.BooleanField(default=False)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    study_group = serializers.IntegerField(required=False, allow_null=True)
    author = serializers.IntegerField(required=False)

    class Meta:
        model = Recruitment
        fields = "__all__"


class RecruitmentDetailSerializer(RecruitmentSerializer):
    """추가 세부 정보를 반환할 수 있는 상세 시리얼라이저"""

    pass
