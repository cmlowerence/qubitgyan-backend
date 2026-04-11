from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()

def create_notification(user, notification_type, title, message, action_link="", expires_in_days=None):
    """
    The Core Engine for generating a single alert.
    Call this from Spaced Repetition, Assessments, or Analytics.
    """
    expires_at = None
    if expires_in_days:
        expires_at = timezone.now() + timedelta(days=expires_in_days)
        
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        action_link=action_link,
        expires_at=expires_at
    )

def broadcast_system_alert(title, message, action_link="", expires_in_days=30):
    """
    Fires a platform-wide notification to every single active student.
    Deeply optimized to prevent Out-Of-Memory (OOM) crashes at 50,000+ users.
    """
    expires_at = None
    if expires_in_days:
        expires_at = timezone.now() + timedelta(days=expires_in_days)
    
    users_qs = User.objects.filter(is_active=True).only('id')
    
    notifications_generator = (
        Notification(
            user_id=user.id,  
            notification_type='SYSTEM',
            title=title,
            message=message,
            action_link=action_link,
            expires_at=expires_at
        )
        for user in users_qs.iterator(chunk_size=2000)
    )
    
    created_alerts = Notification.objects.bulk_create(notifications_generator, batch_size=2000)
    
    return len(created_alerts)