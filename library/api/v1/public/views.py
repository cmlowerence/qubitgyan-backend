# library\api\v1\public\views.py
from rest_framework import viewsets, permissions, mixins, exceptions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.utils import timezone

from library.models import (
    AdmissionRequest, QuizAttempt, Question, 
    Option, QuestionResponse, Quiz, StudentProgress
)
from library.serializers import AdmissionRequestSerializer, QuizAttemptSerializer, StudentQuizReadSerializer

class PublicAdmissionViewSet(viewsets.ModelViewSet):
    """Spam-protected public endpoint for students to request an account"""
    queryset = AdmissionRequest.objects.all()
    serializer_class = AdmissionRequestSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'admissions' # Limits to 5/day per IP (set in settings.py)

    def get_queryset(self):
        # Public users cannot GET the list of applications
        if self.request.method == 'GET':
            raise exceptions.MethodNotAllowed("GET")
        return super().get_queryset()
class StudentQuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # PATCH 4: Performance Optimization
        # select_related and prefetch_related fetch all nested data in exactly 3 efficient queries, 
        # preventing the database from choking when a student checks their history.
        return QuizAttempt.objects.filter(user=self.request.user) \
            .select_related('quiz__resource') \
            .prefetch_related('responses__question', 'responses__selected_option') \
            .order_by('-start_time')

    @action(detail=False, methods=['post'])
    def submit(self, request):
        quiz_id = request.data.get('quiz_id')
        try:
            quiz = Quiz.objects.get(pk=quiz_id)
        except Quiz.DoesNotExist:
            return Response({"error": "Quiz not found"}, status=404)

        answers_data = request.data.get('answers', [])
        
        # PATCH 3: Multiplier Fix - Track processed questions to prevent duplicate grading
        processed_questions = set()
        
        attempt = QuizAttempt.objects.create(user=request.user, quiz=quiz)
        total_score = 0.0

        for answer in answers_data:
            q_id = answer.get('question_id')
            o_id = answer.get('option_id')

            # Skip if we already graded this question in this payload
            if not q_id or q_id in processed_questions:
                continue

            try:
                # PATCH 2: Cross-Quiz Fix - Ensure question actually belongs to THIS quiz
                question = Question.objects.get(id=q_id, quiz=quiz)
                processed_questions.add(q_id)
                
                selected_option = None
                if o_id:
                    # PATCH 1: Option Spoofing Fix - Ensure option belongs to THIS question
                    selected_option = Option.objects.filter(id=o_id, question=question).first()
                
                # Record the response
                QuestionResponse.objects.create(
                    attempt=attempt, 
                    question=question, 
                    selected_option=selected_option
                )

                # Calculate Marking Logic
                if selected_option:
                    if selected_option.is_correct:
                        total_score += float(question.marks_positive)
                    else:
                        total_score -= float(question.marks_negative)
                        
            except Question.DoesNotExist:
                # If they try to inject a fake/foreign question ID, quietly ignore it
                continue

        # Finalize Attempt
        attempt.total_score = total_score
        attempt.is_completed = True
        attempt.end_time = timezone.now()
        attempt.save()

        # Update standard LMS StudentProgress
        StudentProgress.objects.update_or_create(
            user=request.user,
            resource=quiz.resource,
            defaults={'is_completed': True}
        )

        serializer = self.get_serializer(attempt)
        return Response(serializer.data)

class StudentQuizFetchViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Allows students to fetch a specific quiz payload safely"""
    queryset = Quiz.objects.all()
    serializer_class = StudentQuizReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    # We only use Retrieve (GET /api/v1/public/quizzes/{id}/) so they can't list all quizzes at once