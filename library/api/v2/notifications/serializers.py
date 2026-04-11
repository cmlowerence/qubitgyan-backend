from rest_framework import serializers
from django.utils.timesince import timesince
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 
            'action_link', 'is_read', 'created_at', 'time_ago'
        ]
        read_only_fields = [
            'id', 'notification_type', 'title', 'message', 
            'action_link', 'is_read', 'created_at', 'time_ago'
        ]

    def get_time_ago(self, obj):
        # Grabs the largest unit of time (e.g., "2 hours" from "2 hours, 15 minutes")
        return f"{timesince(obj.created_at).split(',')[0]} ago"


class NotificationManagerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'username', 'notification_type', 'title', 
            'message', 'action_link', 'is_read', 'created_at', 'expires_at'
        ]
        read_only_fields = ['id', 'created_at']