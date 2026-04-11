from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from ..models import Notification
from ..serializers import NotificationSerializer

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        
        # 1. Base Query: Only get alerts for this user that haven't expired
        base_query = Notification.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
            user=request.user
        )
        
        total_unread_count = base_query.filter(is_read=False).count()

        unread_only = request.query_params.get('unread_only', 'false').lower() in ['true', '1']
        if unread_only:
            display_notifications = base_query.filter(is_read=False)
        else:
            display_notifications = base_query
            
        display_notifications = display_notifications.order_by('-created_at')[:50]
        
        return Response({
            "unread_count": total_unread_count,
            "notifications": NotificationSerializer(display_notifications, many=True).data
        }, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        return Response(status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        
        updated_count = Notification.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
            user=request.user, 
            is_read=False
        ).update(is_read=True)
        
        return Response({"marked_read_count": updated_count}, status=status.HTTP_200_OK)