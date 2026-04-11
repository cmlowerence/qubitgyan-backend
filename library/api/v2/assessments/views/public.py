from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from library.models import KnowledgeNode
from ..models import Question, QuizAttempt, AttemptAnswer
from ..serializers import (
    QuizAttemptSerializer, 
    QuestionPublicSerializer, 
    QuestionResultSerializer,
    AttemptAnswerSerializer
)
from library.api.v2.analytics.utils import log_user_activity


class QuizGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        topic_id = request.data.get('topic_id')
        question_count = int(request.data.get('question_count', 10))
        
        topic = get_object_or_404(KnowledgeNode, id=topic_id) if topic_id else None
        
        questions_query = Question.objects.filter(is_active=True)
        if topic:
            questions_query = questions_query.filter(topic=topic)
            
        questions = list(questions_query.order_by('?')[:question_count])
        
        if not questions:
            return Response({"error": "No questions available for this topic."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                user=request.user,
                topic=topic,
                total_questions=len(questions)
            )
            
            answers_to_create = [
                AttemptAnswer(attempt=attempt, question=q) for q in questions
            ]
            AttemptAnswer.objects.bulk_create(answers_to_create)

        return Response({
            "attempt": QuizAttemptSerializer(attempt).data,
            "questions": QuestionPublicSerializer(questions, many=True).data
        }, status=status.HTTP_201_CREATED)


class QuizAnswerSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
        
        if attempt.is_completed:
            return Response({"error": "Cannot modify answers after submission."}, status=status.HTTP_403_FORBIDDEN)
            
        question_id = request.data.get('question_id')
        answer = get_object_or_404(AttemptAnswer, attempt=attempt, question_id=question_id)
        
        selected_option_ids = request.data.get('selected_options', [])
        time_spent = request.data.get('time_spent_seconds', 0)
        
        answer.selected_options.set(selected_option_ids)
        answer.time_spent_seconds = time_spent
        answer.save(update_fields=['time_spent_seconds'])
        
        return Response(status=status.HTTP_200_OK)


class QuizCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
        
        if attempt.is_completed:
            return Response({"error": "Quiz already completed."}, status=status.HTTP_400_BAD_REQUEST)

        answers = list(attempt.answers.select_related('question').prefetch_related('selected_options', 'question__options'))
        
        correct_count = 0
        incorrect_count = 0
        total_score = 0
        
        with transaction.atomic():
            for ans in answers:
                selected_ids = {opt.id for opt in ans.selected_options.all()}
                
                if not selected_ids:
                    continue
                
                correct_ids = {opt.id for opt in ans.question.options.all() if opt.is_correct}
                
                if selected_ids == correct_ids:
                    ans.is_correct = True
                    ans.score_earned = ans.question.positive_marks
                    correct_count += 1
                else:
                    ans.is_correct = False
                    ans.score_earned = -ans.question.negative_marks
                    incorrect_count += 1
                    
                total_score += ans.score_earned
            
            AttemptAnswer.objects.bulk_update(answers, ['is_correct', 'score_earned'])
            
            attempt.correct_answers = correct_count
            attempt.incorrect_answers = incorrect_count
            attempt.total_score = total_score
            attempt.end_time = timezone.now()
            attempt.is_completed = True
            attempt.save()

            if attempt.total_questions > 0 and (correct_count / attempt.total_questions) >= 0.5:
                xp_reward = int(total_score) * 2 if total_score > 0 else 10
                log_user_activity(
                    request.user, 
                    quizzes_passed=1, 
                    xp_earned=xp_reward,
                    learning_minutes=max(1, attempt.duration_seconds // 60)
                )

        return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_200_OK)


class QuizReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt.objects.prefetch_related('answers__question__options', 'answers__selected_options'), 
            id=attempt_id, 
            user=request.user
        )
        
        if not attempt.is_completed:
            return Response({"error": "You must complete the quiz to review answers."}, status=status.HTTP_403_FORBIDDEN)

        questions = [ans.question for ans in attempt.answers.all()]
        answers_data = AttemptAnswerSerializer(attempt.answers.all(), many=True).data
        
        return Response({
            "attempt": QuizAttemptSerializer(attempt).data,
            "questions": QuestionResultSerializer(questions, many=True).data,
            "student_answers": answers_data
        }, status=status.HTTP_200_OK)