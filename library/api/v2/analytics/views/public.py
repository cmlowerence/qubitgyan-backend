from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta, datetime

from ..models import DailyUserActivity
from ..serializers import DailyUserActivitySerializer, LeaderboardSerializer

class UserDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = int(request.query_params.get('days', '30'))
            days = max(1, min(days, 365))
        except ValueError:
            days = 30

        start_date = timezone.now().date() - timedelta(days=days)

        activities = DailyUserActivity.objects.filter(
            user=request.user,
            date__gte=start_date
        ).order_by('-date')

        return Response(DailyUserActivitySerializer(activities, many=True).data, status=status.HTTP_200_OK)


class DailyLeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get('date')
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            target_date = timezone.now().date()

        top_users = DailyUserActivity.objects.select_related(
            'user', 'user__profile'
        ).filter(
            date=target_date,
            xp_earned__gt=0
        ).order_by('-xp_earned')[:10]

        return Response(LeaderboardSerializer(top_users, many=True).data, status=status.HTTP_200_OK)