from rest_framework import serializers
from .models import UserWordMastery, ReviewLog
from library.api.v2.lexicon.serializers import WordSerializer

class UserWordMasterySerializer(serializers.ModelSerializer):
    word_details = WordSerializer(source='word', read_only=True)

    class Meta:
        model = UserWordMastery
        fields = [
            'id', 'word', 'word_details', 'status', 'custom_note',
            'easiness_factor', 'interval', 'repetitions',
            'next_review_date', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'easiness_factor', 'interval', 'repetitions',
            'next_review_date', 'created_at', 'updated_at'
        ]

class ReviewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewLog
        fields = [
            'id', 'user', 'word', 'grade', 'duration_seconds', 'review_datetime'
        ]
        read_only_fields = ['user', 'review_datetime']

    def validate_grade(self, value):
        """
        Enforce the SM-2 algorithm's strict 0-5 grading scale.
        0 = Complete blackout
        1 = Incorrect, but remembered once seen
        2 = Incorrect, but seemed easy
        3 = Correct, but with significant effort
        4 = Correct, after some hesitation
        5 = Perfect, immediate recall
        """
        if not (0 <= value <= 5):
            raise serializers.ValidationError("Grade must be an integer between 0 and 5 to satisfy the SM-2 algorithm.")
        return value

    def validate_duration_seconds(self, value):
        """Prevent negative time logging."""
        if value < 0:
            raise serializers.ValidationError("Duration cannot be negative.")
        return value