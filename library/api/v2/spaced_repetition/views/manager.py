from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone  # CRITICAL IMPORT ADDED

from ..models import UserWordMastery, ReviewLog
from ..serializers import UserWordMasterySerializer, ReviewLogSerializer

User = get_user_model()

class StudentMasteryListView(APIView):
    """
    Allows Admins to audit a specific student's flashcard deck and progress.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, user_id):
        student = get_object_or_404(User, id=user_id)
        
        status_filter = request.query_params.get('status')
        mastery_records = UserWordMastery.objects.filter(user=student)
        
        if status_filter and status_filter.upper() in dict(UserWordMastery.STATUS_CHOICES).keys():
            mastery_records = mastery_records.filter(status=status_filter.upper())
            
        mastery_records = mastery_records.order_by('-updated_at')
        
        serializer = UserWordMasterySerializer(mastery_records[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentReviewLogAuditView(APIView):
    """
    Allows Admins to see a student's exact interaction history to catch
    spam-clicking or identify exactly when they started struggling.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, user_id):
        student = get_object_or_404(User, id=user_id)
        
        # Get their last 100 card flips
        logs = ReviewLog.objects.filter(user=student).order_by('-review_datetime')[:100]
        
        serializer = ReviewLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResetStudentMasteryView(APIView):
    """
    The 'Emergency Reset' button. Wipes algorithmic progress and forces
    the card back into the student's immediate daily queue.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, user_id, word_id):
        student = get_object_or_404(User, id=user_id)
        mastery = get_object_or_404(UserWordMastery, user=student, word_id=word_id)
        
        # CRITICAL FIX: Factory Reset the SM-2 Math AND the calendar date
        mastery.status = 'NEW'
        mastery.easiness_factor = 2.5
        mastery.interval = 0
        mastery.repetitions = 0
        mastery.custom_note = None
        mastery.next_review_date = timezone.now().date() # Forces it into today's deck
        
        mastery.save()

        return Response(
            {
                "message": f"Mastery for word ID {word_id} has been completely reset for user {student.username}.",
                "data": UserWordMasterySerializer(mastery).data
            },
            status=status.HTTP_200_OK
        )