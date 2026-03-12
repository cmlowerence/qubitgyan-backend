from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from ..models import StudyPlan, StudyTask
from ..serializers import StudyPlanSerializer, StudyTaskSerializer

User = get_user_model()

class AllStudyPlansListView(APIView):
    """
    Platform-wide view for Admins to monitor all generated study plans.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        plans = StudyPlan.objects.select_related('user', 'course').all().order_by('-created_at')
        
        status_filter = request.query_params.get('status')
        if status_filter and status_filter.upper() in dict(StudyPlan.STATUS_CHOICES).keys():
            plans = plans.filter(status=status_filter.upper())
            
        serializer = StudyPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminStudyPlanDetailView(APIView):
    """
    Deep-dive into a specific plan. Allows Admins to view all tasks, 
    force-update the plan's status, or delete it entirely.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, plan_id):
        plan = get_object_or_404(StudyPlan.objects.select_related('user', 'course'), id=plan_id)
        
        tasks = StudyTask.objects.filter(plan=plan).select_related('topic').order_by('scheduled_date')
        
        return Response({
            "plan": StudyPlanSerializer(plan).data,
            "tasks": StudyTaskSerializer(tasks, many=True).data
        }, status=status.HTTP_200_OK)

    def patch(self, request, plan_id):
        """Force-update the status (e.g., Admin marking an abandoned plan as 'PAUSED')"""
        plan = get_object_or_404(StudyPlan, id=plan_id)
        new_status = request.data.get('status')
        
        if new_status and new_status.upper() in dict(StudyPlan.STATUS_CHOICES).keys():
            plan.status = new_status.upper()
            plan.save(update_fields=['status', 'updated_at'])
            return Response(StudyPlanSerializer(plan).data, status=status.HTTP_200_OK)
            
        return Response({"error": "Invalid status provided."}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, plan_id):
        """Emergency cleanup. Deleting the plan automatically cascades to all tasks."""
        plan = get_object_or_404(StudyPlan, id=plan_id)
        plan.delete()
        return Response({"message": "Study plan and all associated tasks permanently deleted."}, status=status.HTTP_204_NO_CONTENT)