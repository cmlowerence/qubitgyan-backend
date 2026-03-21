import uuid
from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPE_CHOICES = [
        ('SYSTEM', 'System Announcement'),
        ('REMINDER', 'Study Reminder'),
        ('ACHIEVEMENT', 'Achievement Unlocked'),
        ('ALERT', 'Account Alert'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SYSTEM')
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    action_link = models.CharField(max_length=255, blank=True)
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] UserID:{self.user_id} - {self.title[:30]}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])