from rest_framework import serializers
from .models import Question, QuestionOption, QuizAttempt, AttemptAnswer

# ==========================================
# PUBLIC SERIALIZERS (During the Test)
# ==========================================

class QuestionOptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_fixed_position']
        read_only_fields = fields


class QuestionPublicSerializer(serializers.ModelSerializer):
    options = QuestionOptionPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'topic', 'topic_name_snapshot', 'question_type', 
            'text', 'difficulty', 'positive_marks', 'negative_marks', 'options'
        ]
        read_only_fields = fields


# ==========================================
# RESULT SERIALIZERS (After the Test)
# ==========================================

class QuestionOptionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_correct', 'is_fixed_position']
        read_only_fields = fields


class QuestionResultSerializer(serializers.ModelSerializer):
    options = QuestionOptionResultSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'topic', 'question_type', 'text', 'explanation', 
            'difficulty', 'positive_marks', 'negative_marks', 'options'
        ]
        read_only_fields = fields


# ==========================================
# ATTEMPT & ANSWER SERIALIZERS
# ==========================================

class QuizAttemptSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'user', 'topic', 'start_time', 'end_time', 
            'total_questions', 'correct_answers', 'incorrect_answers', 
            'total_score', 'is_completed', 'duration_seconds'
        ]
        read_only_fields = [
            'user', 'start_time', 'end_time', 'total_questions', 
            'correct_answers', 'incorrect_answers', 'total_score', 
            'is_completed', 'duration_seconds'
        ]


class AttemptAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttemptAnswer
        fields = [
            'id', 'attempt', 'question', 'selected_options', 
            'is_correct', 'score_earned', 'time_spent_seconds'
        ]
        read_only_fields = ['is_correct', 'score_earned']


# ==========================================
# MANAGER SERIALIZERS (Admin Dashboard)
# ==========================================

class QuestionOptionManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_correct', 'is_fixed_position']


class QuestionManagerSerializer(serializers.ModelSerializer):
    options = QuestionOptionManagerSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'topic', 'question_type', 'text', 'explanation', 
            'difficulty', 'positive_marks', 'negative_marks', 
            'is_active', 'created_at', 'options'
        ]