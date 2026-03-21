import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from library.models import KnowledgeNode

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('EASY', 'Easy'),
        ('MEDIUM', 'Medium'),
        ('HARD', 'Hard'),
    ]
    TYPE_CHOICES = [
        ('SINGLE', 'Single Choice'),
        ('MULTIPLE', 'Multiple Choice'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.ForeignKey(KnowledgeNode, on_delete=models.SET_NULL, null=True, related_name='questions')
    topic_name_snapshot = models.CharField(max_length=255, blank=True)
    
    question_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='SINGLE')
    text = models.TextField(help_text="Supports Markdown and LaTeX for math equations.")
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='MEDIUM')
    
    positive_marks = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    negative_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['topic', 'difficulty', 'is_active']),
        ]

    def __str__(self):
        return f"{self.text[:50]}..."

    def save(self, *args, **kwargs):
        if self.topic and self.topic_name_snapshot != self.topic.name:
            self.topic_name_snapshot = self.topic.name
        super().save(*args, **kwargs)


class QuestionOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    
    text = models.TextField(help_text="Supports Markdown and LaTeX.")
    is_correct = models.BooleanField(default=False)
    is_fixed_position = models.BooleanField(default=False, help_text="True for 'All of the above' options so they don't shuffle.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['question', 'text'], name='unique_option_per_question')
        ]

    def __str__(self):
        return self.text[:50]


class QuizAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assessment_attempts')
    
    topic = models.ForeignKey(KnowledgeNode, on_delete=models.SET_NULL, null=True)
    
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    incorrect_answers = models.PositiveIntegerField(default=0)
    
    total_score = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    is_completed = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_completed', '-start_time']),
        ]
        ordering = ['-start_time']

    @property
    def duration_seconds(self):
        if not self.end_time:
            return 0
        return int((self.end_time - self.start_time).total_seconds())


class AttemptAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    
    selected_options = models.ManyToManyField(QuestionOption, blank=True)
    
    is_correct = models.BooleanField(default=False)
    score_earned = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['attempt', 'question'], name='unique_question_per_attempt')
        ]