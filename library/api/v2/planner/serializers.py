from rest_framework import serializers
from django.utils import timezone
from .models import StudyPlan, StudyTask

class StudyPlanSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.title', read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = StudyPlan
        fields = [
            'id', 'user', 'course', 'course_name', 'title', 'target_exam_date', 
            'status', 'days_remaining', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user', 'status', 'days_remaining', 'created_at', 'updated_at'
        ]

    def validate_target_exam_date(self, value):
        if value <= timezone.now().date():
            raise serializers.ValidationError("Target exam date must be in the future.")
        return value

class StudyTaskSerializer(serializers.ModelSerializer):
    topic_name = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = StudyTask
        fields = [
            'id', 'plan', 'topic', 'topic_name', 'scheduled_date', 
            'is_completed', 'completed_at', 'is_overdue'
        ]
        read_only_fields = [
            'is_completed', 'completed_at', 'is_overdue', 'topic_name'
        ]

    def get_topic_name(self, obj):
        return obj.topic.name if obj.topic else obj.topic_name_snapshot