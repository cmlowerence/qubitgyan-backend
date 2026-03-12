from django.urls import path
from .views.public import StudyPlanListCreateView, DailyTasksView, TaskToggleView
from .views.manager import AllStudyPlansListView, AdminStudyPlanDetailView

urlpatterns = [
    # GET: List student's plans | POST: Generate a new 90-day roadmap
    path('public/plans/', StudyPlanListCreateView.as_view(), name='planner-public-plans'),
    
    # GET: Fetch tasks for a specific date (defaults to today)
    path('public/tasks/daily/', DailyTasksView.as_view(), name='planner-public-daily-tasks'),
    
    # PATCH: Mark a specific task as Done/Undone
    path('public/tasks/<uuid:task_id>/toggle/', TaskToggleView.as_view(), name='planner-public-task-toggle'),

    # GET: View all study plans across QubitGyan
    path('manager/plans/', AllStudyPlansListView.as_view(), name='planner-manager-all-plans'),
    
    # GET, PATCH, DELETE: Manage a specific study plan and its underlying tasks
    path('manager/plans/<uuid:plan_id>/', AdminStudyPlanDetailView.as_view(), name='planner-manager-plan-detail'),
]