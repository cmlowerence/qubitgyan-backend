from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from datetime import timedelta
import math

from ..models import StudyPlan, StudyTask
from ..serializers import StudyPlanSerializer, StudyTaskSerializer
from library.models import Course, KnowledgeNode

class StudyPlanListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = StudyPlan.objects.select_related('course').filter(user=request.user)
        return Response(StudyPlanSerializer(plans, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = StudyPlanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        course = serializer.validated_data['course']
        target_date = serializer.validated_data['target_exam_date']

        if StudyPlan.objects.filter(user=request.user, course=course, status='ACTIVE').exists():
            return Response(
                {"error": "You already have an active plan for this course."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        topics = self._extract_course_topics(course)
        if not topics:
            return Response(
                {"error": "This course curriculum is currently empty. Cannot generate a plan."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            plan = serializer.save(user=request.user)
            self._schedule_daily_tasks(plan, topics, target_date)

        return Response(StudyPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    def _extract_course_topics(self, course):
        """Safely extracts all v1 active TOPIC nodes from the KnowledgeNode tree."""
        if not course.root_node:
            return []

        l1 = [course.root_node.id]
        l2 = list(KnowledgeNode.objects.filter(parent_id__in=l1).values_list('id', flat=True))
        l3 = list(KnowledgeNode.objects.filter(parent_id__in=l2).values_list('id', flat=True))
        l4 = list(KnowledgeNode.objects.filter(parent_id__in=l3).values_list('id', flat=True))
        
        all_node_ids = set(l1 + l2 + l3 + l4)
        
        return list(KnowledgeNode.objects.filter(
            id__in=all_node_ids, 
            node_type='TOPIC', 
            is_active=True
        ).order_by('order', 'id'))

    def _schedule_daily_tasks(self, plan, topics, target_date):
        """Mathematically distributes the topics across the available days."""
        today = timezone.now().date()
        total_days = max(1, (target_date - today).days)
        topics_per_day = math.ceil(len(topics) / total_days)
        
        tasks_to_create = []
        current_date = today
        topic_index = 0

        while topic_index < len(topics) and current_date < target_date:
            daily_topics = topics[topic_index : topic_index + topics_per_day]
            
            for topic in daily_topics:
                tasks_to_create.append(
                    StudyTask(
                        plan=plan,
                        topic=topic,
                        topic_name_snapshot=topic.name,
                        scheduled_date=current_date
                    )
                )
            
            topic_index += topics_per_day
            current_date += timedelta(days=1)

        if tasks_to_create:
            StudyTask.objects.bulk_create(tasks_to_create)


class DailyTasksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get('date')
        if date_str:
            try:
                target_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = timezone.now().date()

        tasks = StudyTask.objects.select_related('plan', 'topic').filter(
            plan__user=request.user,
            plan__status='ACTIVE',
            scheduled_date=target_date
        )

        return Response(StudyTaskSerializer(tasks, many=True).data, status=status.HTTP_200_OK)


class TaskToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, task_id):
        task = get_object_or_404(
            StudyTask.objects.select_related('plan'), 
            id=task_id, 
            plan__user=request.user
        )
        
        raw_status = request.data.get('is_completed')
        
        if raw_status in [True, 'true', 'True', 1, '1']:
            is_completed = True
        elif raw_status in [False, 'false', 'False', 0, '0']:
            is_completed = False
        else:
            return Response({"error": "Invalid boolean for is_completed"}, status=status.HTTP_400_BAD_REQUEST)
        
        if is_completed:
            task.mark_completed()
        else:
            task.is_completed = False
            task.completed_at = None
            task.save(update_fields=['is_completed', 'completed_at'])

        return Response(StudyTaskSerializer(task).data, status=status.HTTP_200_OK)