from rest_framework import viewsets, filters, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Count
from django.contrib.auth.models import User

from .models import KnowledgeNode, Resource, ProgramContext, StudentProgress
from .serializers import (
    KnowledgeNodeSerializer, ResourceSerializer, 
    ProgramContextSerializer, UserSerializer, StudentProgressSerializer
)
from .permissions import IsAdminOrReadOnly

class ProgramContextViewSet(viewsets.ModelViewSet):
    queryset = ProgramContext.objects.all()
    serializer_class = ProgramContextSerializer
    permission_classes = [IsAdminOrReadOnly]

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'contexts__name']

    def get_queryset(self):
        queryset = Resource.objects.all()
        
        # Filter by Node ID
        node_id = self.request.query_params.get('node', None)
        if node_id:
            queryset = queryset.filter(node_id=node_id)

        # Filter by Context Name (e.g., JEE)
        context_name = self.request.query_params.get('context', None)
        if context_name:
            queryset = queryset.filter(contexts__name__icontains=context_name)

        return queryset

class KnowledgeNodeViewSet(viewsets.ModelViewSet):
    # Annotate with resource_count for UI badges
    queryset = KnowledgeNode.objects.annotate(resource_count=Count('resources'))
    serializer_class = KnowledgeNodeSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        # "All=True" returns flat list (good for dropdowns)
        if self.request.query_params.get('all', 'false').lower() == 'true':
            return KnowledgeNode.objects.annotate(resource_count=Count('resources'))
        # Default: Return Tree Roots
        return KnowledgeNode.objects.filter(parent__isnull=True).annotate(resource_count=Count('resources'))

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    # Endpoint for App to identify current user
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

class StudentProgressViewSet(viewsets.ModelViewSet):
    serializer_class = StudentProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Students only see their own progress
        return StudentProgress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Auto-link progress to logged-in user
        serializer.save(user=self.request.user)

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response({
            "total_nodes": KnowledgeNode.objects.count(),
            "active_users": User.objects.count(),
            "total_resources": Resource.objects.count(),
            "storage_used": "N/A", 
        })
