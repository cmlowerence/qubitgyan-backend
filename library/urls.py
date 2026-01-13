from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    KnowledgeNodeViewSet, ResourceViewSet, 
    ProgramContextViewSet, UserViewSet, 
    StudentProgressViewSet, DashboardStatsView,
    GlobalSearchView  # The new addition
)

router = DefaultRouter()
router.register(r'nodes', KnowledgeNodeViewSet, basename='node')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'contexts', ProgramContextViewSet, basename='context')
router.register(r'users', UserViewSet, basename='user')
router.register(r'progress', StudentProgressViewSet, basename='progress')

urlpatterns = [
    path('', include(router.urls)),
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    # Add this here so it's accessible at /api/v1/global-search/
    path('global-search/', GlobalSearchView.as_view(), name='global-search'),
]
