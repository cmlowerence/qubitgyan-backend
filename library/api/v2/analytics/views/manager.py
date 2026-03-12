from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from ..models import DailyUserActivity
from ..serializers import DailyUserActivitySerializer

User = get_user_model()

class AdminStudentActivityView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, user_id):
        if not User.objects.filter(id=user_id).exists():
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        activities = DailyUserActivity.objects.filter(user_id=user_id).order_by('-date')[:100]
        
        return Response(DailyUserActivitySerializer(activities, many=True).data, status=status.HTTP_200_OK)


class AdminActivityCorrectionView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, activity_id):
        activity = get_object_or_404(DailyUserActivity, id=activity_id)
        
        allowed_fields = [
            'learning_minutes', 'flashcards_reviewed', 
            'tasks_completed', 'quizzes_passed', 'xp_earned'
        ]
        update_fields = []
        
        for field in allowed_fields:
            if field in request.data:
                val = request.data[field]
                
                if isinstance(val, bool) or not isinstance(val, int):
                    if isinstance(val, str) and val.isdigit():
                        val = int(val)
                    else:
                        return Response(
                            {"error": f"Strict integer required for {field}."}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                if val >= 0:
                    setattr(activity, field, val)
                    update_fields.append(field)
                else:
                    return Response(
                        {"error": f"{field} cannot be negative."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        if update_fields:
            activity.save(update_fields=update_fields)
            
        return Response(DailyUserActivitySerializer(activity).data, status=status.HTTP_200_OK)