import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Q

from library.models import Course, KnowledgeNode 

class StudyPlan(models.Model):
    """
    The macro-level roadmap for a student. 
    Tracks their target exam date and overall completion status.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('ABANDONED', 'Abandoned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_plans')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='generated_plans')
    
    title = models.CharField(max_length=255, help_text="e.g., 'TGT Physics 90-Day Sprint'")
    target_exam_date = models.DateField(db_index=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Study Plans"
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'course'], 
                condition=Q(status='ACTIVE'), 
                name='unique_active_plan_per_course'
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.title} ({self.status})"

    @property
    def days_remaining(self):
        delta = self.target_exam_date - timezone.now().date()
        return max(0, delta.days)


class StudyTask(models.Model):
    """
    The micro-level daily milestone. 
    Links a specific day on the calendar to a specific topic in your v1 tree.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name='daily_tasks')
    
    topic = models.ForeignKey(KnowledgeNode, on_delete=models.SET_NULL, null=True, related_name='planned_tasks')
    
    topic_name_snapshot = models.CharField(max_length=255, blank=True, help_text="Saves the name if the linked topic is deleted")
    
    scheduled_date = models.DateField()
    
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['plan', 'scheduled_date']),
            models.Index(fields=['is_completed', 'scheduled_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['plan', 'topic', 'scheduled_date'], 
                name='unique_daily_topic_per_plan'
            )
        ]
        ordering = ['scheduled_date'] # Removed topic__order since topic can now be null

    def __str__(self):
        topic_name = self.topic.name if self.topic else self.topic_name_snapshot
        return f"{self.scheduled_date}: {topic_name} ({'Done' if self.is_completed else 'Pending'})"

    def save(self, *args, **kwargs):
        if self.topic and self.topic_name_snapshot != self.topic.name:
            self.topic_name_snapshot = self.topic.name
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        if self.is_completed:
            return False
        return self.scheduled_date < timezone.now().date()

    def mark_completed(self):
        """Secure method to handle completion logic."""
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'completed_at'])