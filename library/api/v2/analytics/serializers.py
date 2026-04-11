from rest_framework import serializers
from .models import DailyUserActivity

class DailyUserActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyUserActivity
        fields = [
            'id', 'date', 'learning_minutes', 
            'flashcards_reviewed', 'tasks_completed', 
            'quizzes_passed', 'xp_earned'
        ]
        read_only_fields = fields

class LeaderboardSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = DailyUserActivity
        fields = [
            'username', 'first_name', 'last_name', 'avatar_url', 'xp_earned'
        ]

    def get_avatar_url(self, obj):
        if hasattr(obj.user, 'profile') and obj.user.profile.avatar_url:
            return obj.user.profile.avatar_url
        return None