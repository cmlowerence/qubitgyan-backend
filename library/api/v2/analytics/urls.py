from django.urls import path
from .views.public import UserDashboardStatsView, DailyLeaderboardView
from .views.manager import AdminStudentActivityView, AdminActivityCorrectionView

urlpatterns = [
    # PUBLIC ENDPOINTS
    path('public/dashboard/', UserDashboardStatsView.as_view(), name='analytics-public-dashboard'),
    path('public/leaderboard/', DailyLeaderboardView.as_view(), name='analytics-public-leaderboard'),

    # MANAGER ENDPOINTS
    path('manager/students/<int:user_id>/activities/', AdminStudentActivityView.as_view(), name='analytics-manager-student-activities'),
    path('manager/activities/<uuid:activity_id>/', AdminActivityCorrectionView.as_view(), name='analytics-manager-activity-correction'),
]