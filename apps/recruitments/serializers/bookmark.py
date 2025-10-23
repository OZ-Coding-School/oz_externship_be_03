from rest_framework import serializers

from apps.recruitments.models.bookmark import Bookmark


class BookmarkSerializer(serializers.ModelSerializer[Bookmark]):

    class Meta:
        model = Bookmark
        fields = ["user_id", "recruitment_id", "created_at"]
        read_only_fields = ["created_at"]
