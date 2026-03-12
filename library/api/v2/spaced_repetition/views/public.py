from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import UserWordMastery
from ..serializers import UserWordMasterySerializer, ReviewLogSerializer
from library.api.v2.lexicon.models import Word

class DueFlashcardsView(APIView):
    """
    Fetches the deck of words the student needs to review today.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        
        due_cards = UserWordMastery.objects.select_related('word').prefetch_related(
            'word__categories',
            'word__pronunciations',
            'word__meanings',
            'word__thesaurus_entries'
        ).filter(
            user=request.user,
            next_review_date__lte=today
        ).exclude(status='IGNORED').order_by('next_review_date')

        serializer = UserWordMasterySerializer(due_cards[:50], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SubmitReviewView(APIView):
    """
    The Core Engine. Receives a grade (0-5) and calculates the next review date.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReviewLogSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        word = serializer.validated_data['word']
        grade = serializer.validated_data['grade']

        with transaction.atomic():
            serializer.save(user=request.user)

            mastery, created = UserWordMastery.objects.get_or_create(
                user=request.user,
                word=word,
                defaults={'status': 'NEW'}
            )

            # --- THE SM-2 ALGORITHM MATH ---
            if grade >= 3:
                if mastery.repetitions == 0:
                    mastery.interval = 1
                elif mastery.repetitions == 1:
                    mastery.interval = 6
                else:
                    mastery.interval = round(mastery.interval * mastery.easiness_factor)
                mastery.repetitions += 1
            else:
                mastery.repetitions = 0
                mastery.interval = 1

            # Update Easiness Factor (EF)
            new_ef = mastery.easiness_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
            mastery.easiness_factor = max(1.3, new_ef)

            mastery.next_review_date = timezone.now().date() + timedelta(days=mastery.interval)
            
            # --- STATUS UPGRADES ---
            if mastery.status == 'NEW':
                mastery.status = 'LEARNING'
            if mastery.repetitions >= 4 and mastery.status != 'IGNORED':
                mastery.status = 'MASTERED'
            elif grade < 3 and mastery.status == 'MASTERED':
                mastery.status = 'LEARNING'

            mastery.save()

        return Response(UserWordMasterySerializer(mastery).data, status=status.HTTP_200_OK)


class WordInteractionView(APIView):
    """
    Allows the student to completely mute a word ("I already know this") 
    or attach a custom mnemonic hint to it.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, word_id):
        word = get_object_or_404(Word, id=word_id)
        mastery, created = UserWordMastery.objects.get_or_create(
            user=request.user,
            word=word
        )
        
        new_status = request.data.get('status')
        custom_note = request.data.get('custom_note')

        if new_status and new_status in dict(UserWordMastery.STATUS_CHOICES).keys():
            mastery.status = new_status
        if custom_note is not None:
            mastery.custom_note = custom_note
            
        mastery.save()
        return Response(UserWordMasterySerializer(mastery).data, status=status.HTTP_200_OK)