from django.urls import path
from .views.public import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView
)
from .views.manager import (
    BroadcastSystemAlertView,
    AdminNotificationLogView
)

urlpatterns = [
    # GET: Fetch the latest 50 alerts and the unread badge count
    path('public/', NotificationListView.as_view(), name='notification-public-list'),
    
    # PATCH: Mark a single specific notification as read
    path('public/<uuid:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-public-mark-read'),
    
    # POST: Instantly mark all unread notifications as read (Bulk action)
    path('public/read-all/', NotificationMarkAllReadView.as_view(), name='notification-public-mark-all-read'),
    # POST: Broadcast a system-wide alert to 50,000+ students instantly
    path('manager/broadcast/', BroadcastSystemAlertView.as_view(), name='notification-manager-broadcast'),
    
    # GET: View aggregated analytics of past system broadcasts
    path('manager/logs/', AdminNotificationLogView.as_view(), name='notification-manager-logs'),
]