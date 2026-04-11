import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from library.api.v2.lexicon.models import Word

class UserWordMastery(models.Model):
    """
    Tracks a student's progress on a specific word using the SM-2 Algorithm.
    """
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('LEARNING', 'Learning'),
        ('MASTERED', 'Mastered'),
        ('IGNORED', 'Ignored/Muted'), 
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='word_mastery')
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='user_mastery')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='NEW')
    custom_note = models.TextField(blank=True, null=True, help_text="Student's personal mnemonic or hint")
    
    easiness_factor = models.FloatField(default=2.5)
    interval = models.IntegerField(default=0)
    repetitions = models.IntegerField(default=0)
    next_review_date = models.DateField(default=timezone.now)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'word'], name='unique_user_word_mastery')
        ]
        verbose_name_plural = "User Word Masteries"

    def __str__(self):
        return f"{self.user} - {self.word.text} [{self.status}]"


class ReviewLog(models.Model):
    """
    A lightweight ledger tracking every single flashcard review.
    Crucial for dashboard analytics, heatmaps, and gamification streaks.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_logs')
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    
    grade = models.IntegerField() 
    
    duration_seconds = models.IntegerField(default=0) 
    
    review_datetime = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-review_datetime']
        indexes = [
            models.Index(fields=['user', 'review_datetime']),
        ]

    def __str__(self):
        return f"{self.user} reviewed {self.word.text} (Grade: {self.grade})"
    

