from rest_framework.serializers import ModelSerializer

from apps.recruitments.models.search_log import SearchLog


class SearchLogSerializer(ModelSerializer[SearchLog]):
    class Meta:
        model = SearchLog
        fields = [
            "id",
            "user",
            "q",
            "filters",
            "results_count",
            "latency_ms",
            "ip",
            "user_agent",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "results_count",
            "latency_ms",
            "ip",
            "user_agent",
            "created_at",
        ]
