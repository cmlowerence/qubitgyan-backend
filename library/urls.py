# library/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import your existing core views
from .views import (
    KnowledgeNodeViewSet, ResourceViewSet, 
    ProgramContextViewSet, UserViewSet, 
    StudentProgressViewSet, DashboardStatsView,
    GlobalSearchView
)

# Import the NEW split views
from .api.v1.public.views import PublicAdmissionViewSet, StudentQuizAttemptViewSet
from .api.v1.manager.views import ManagerAdmissionViewSet, QuizManagementViewSet

router = DefaultRouter()

# --- Core Contract Routes (Unchanged) ---
router.register(r'nodes', KnowledgeNodeViewSet, basename='node')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'contexts', ProgramContextViewSet, basename='context')
router.register(r'users', UserViewSet, basename='user')
router.register(r'progress', StudentProgressViewSet, basename='progress')

# --- NEW: Public Routes ---
router.register(r'public/admissions', PublicAdmissionViewSet, basename='public-admission')
router.register(r'public/quiz-attempts', StudentQuizAttemptViewSet, basename='student-quiz')

# --- NEW: Manager Routes ---
router.register(r'manager/admissions', ManagerAdmissionViewSet, basename='manager-admission')
router.register(r'manager/quizzes', QuizManagementViewSet, basename='manager-quiz')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('global-search/', GlobalSearchView.as_view(), name='global-search'),
]