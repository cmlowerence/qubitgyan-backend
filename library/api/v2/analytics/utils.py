from django.utils import timezone
from django.db import IntegrityError, transaction
from .models import DailyUserActivity

def log_user_activity(user, **kwargs):
    today = timezone.now().date()
    
    try:
        with transaction.atomic():
            activity, created = DailyUserActivity.objects.get_or_create(
                user=user,
                date=today,
                defaults=kwargs
            )
            
            if not created:
                activity.increment_stats(**kwargs)
                
        return activity
        
    except IntegrityError:
        activity = DailyUserActivity.objects.get(user=user, date=today)
        activity.increment_stats(**kwargs)
        return activity