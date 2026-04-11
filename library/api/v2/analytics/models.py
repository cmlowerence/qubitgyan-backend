import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class DailyUserActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_activities')
    date = models.DateField(default=timezone.now)

    learning_minutes = models.PositiveIntegerField(default=0)
    flashcards_reviewed = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    quizzes_passed = models.PositiveIntegerField(default=0)
    xp_earned = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Daily User Activities"
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_daily_activity_per_user')
        ]
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['date', '-xp_earned']),
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} - {self.date} - {self.xp_earned}XP"

    def increment_stats(self, **kwargs):
        update_fields = []
        
        for field, value in kwargs.items():
            if hasattr(self, field) and isinstance(value, int) and value > 0:
                setattr(self, field, models.F(field) + value)
                update_fields.append(field)
        
        if update_fields:
            self.save(update_fields=update_fields)
            self.refresh_from_db(fields=update_fields)