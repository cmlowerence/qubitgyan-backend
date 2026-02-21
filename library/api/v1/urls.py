from django.urls import path, include
from rest_framework.routers import DefaultRouter

from library.api.v1.core.views import (
    KnowledgeNodeViewSet,
    ResourceViewSet,
    ProgramContextViewSet,
    UserViewSet,
    StudentProgressViewSet,
    DashboardStatsView,
    GlobalSearchView,
)
from library.api.v1.public.views import (
    PublicAdmissionViewSet,
    StudentQuizAttemptViewSet,
    StudentQuizFetchViewSet,
    PublicCourseViewSet,
    GamificationViewSet,
    StudentNotificationViewSet,
    ChangePasswordView,
    MyProfileView,
    BookmarkViewSet,
    ResourceTrackingViewSet,
)
from library.api.v1.manager.views import (
    ManagerAdmissionViewSet,
    QuizManagementViewSet,
    EmailManagementViewSet,
    ManagerCourseViewSet,
    ManagerNotificationViewSet,
    SuperAdminRBACViewSet,
    ImageManagementViewSet,
)
from library.api.v1.system.views import HealthCheckView


router = DefaultRouter()

# --- Core Contract Routes ---
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'contexts', ProgramContextViewSet, basename='context')
router.register(r'users', UserViewSet, basename='user')
router.register(r'progress', StudentProgressViewSet, basename='progress')

# --- Public Routes ---
router.register(r'public/admissions', PublicAdmissionViewSet, basename='public-admission')
router.register(r'public/quiz-attempts', StudentQuizAttemptViewSet, basename='student-quiz-attempt')
router.register(r'public/quizzes', StudentQuizFetchViewSet, basename='student-quiz-fetch')
router.register(r'public/courses', PublicCourseViewSet, basename='public-course')
router.register(r'public/gamification', GamificationViewSet, basename='public-gamification')
router.register(r'public/notifications', StudentNotificationViewSet, basename='public-notification')
router.register(r'public/bookmarks', BookmarkViewSet, basename='public-bookmark')
router.register(r'public/tracking', ResourceTrackingViewSet, basename='public-tracking')

# --- Manager Routes ---
router.register(r'manager/nodes', KnowledgeNodeViewSet, basename='manager-nodes')
router.register(r'manager/admissions', ManagerAdmissionViewSet, basename='manager-admission')
router.register(r'manager/quizzes', QuizManagementViewSet, basename='manager-quiz')
router.register(r'manager/emails', EmailManagementViewSet, basename='manager-emails')
router.register(r'manager/courses', ManagerCourseViewSet, basename='manager-course')
router.register(r'manager/notifications', ManagerNotificationViewSet, basename='manager-notification')
router.register(r'manager/rbac', SuperAdminRBACViewSet, basename='manager-rbac')
router.register(r'manager/media', ImageManagementViewSet, basename='manager-media')

urlpatterns = [
    path('health/', HealthCheckView.as_view()),
    path('', include(router.urls)),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('global-search/', GlobalSearchView.as_view(), name='global-search'),
    path('public/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('public/my-profile/', MyProfileView.as_view(), name='my-profile'),
]
