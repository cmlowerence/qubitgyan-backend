from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count, Max

from ..utils import broadcast_system_alert
from ..models import Notification

class BroadcastSystemAlertView(APIView):
    """
    Triggers a platform-wide alert to all active students.
    Strictly locked to Admin users.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        title = request.data.get('title', '').strip()
        message = request.data.get('message', '').strip()
        action_link = request.data.get('action_link', '').strip()
        
        if not title or not message:
            return Response(
                {"error": "Both 'title' and 'message' are required to broadcast an alert."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(title) > 255:
            return Response({"error": "Title cannot exceed 255 characters."}, status=status.HTTP_400_BAD_REQUEST)
            
        if len(action_link) > 255:
            return Response({"error": "Action link cannot exceed 255 characters."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            expires_in_days = int(request.data.get('expires_in_days', 30))
            if expires_in_days <= 0:
                return Response({"error": "expires_in_days must be a positive integer greater than 0."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "expires_in_days must be a valid integer."}, status=status.HTTP_400_BAD_REQUEST)


        try:
            users_notified_count = broadcast_system_alert(
                title=title,
                message=message,
                action_link=action_link,
                expires_in_days=expires_in_days
            )
        except Exception as e:
            # Catching unforeseen DB limits or connection drops during the massive bulk insert
            return Response({"error": f"Broadcast failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": "System alert broadcast successfully.",
            "users_notified": users_notified_count
        }, status=status.HTTP_201_CREATED)


class AdminNotificationLogView(APIView):
    """
    Aggregates the massive system alerts table so Admins can see
    a clean history of exactly what broadcasts were sent and to how many users.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        broadcast_history = Notification.objects.filter(
            notification_type='SYSTEM'
        ).values(
            'title', 'message', 'action_link'
        ).annotate(
            total_recipients=Count('id'),
            broadcast_date=Max('created_at')
        ).order_by('-broadcast_date')[:50]
        
        return Response(broadcast_history, status=status.HTTP_200_OK)