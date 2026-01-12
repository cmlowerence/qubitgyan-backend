from django.urls import path, include
from rest_framework.routers import DefaultRouter  # <--- FIXED IMPORT
from .views import KnowledgeNodeViewSet, ResourceViewSet, ProgramContextViewSet

router = DefaultRouter()
router.register(r'nodes', KnowledgeNodeViewSet, basename='node')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'contexts', ProgramContextViewSet, basename='context')

urlpatterns = [
    path('', include(router.urls)),
]
