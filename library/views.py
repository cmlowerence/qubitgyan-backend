from rest_framework import viewsets, filters, permissions, status
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
        node_id = self.request.query_params.get('node', None)
        if node_id:
            queryset = queryset.filter(node_id=node_id)

        context_name = self.request.query_params.get('context', None)
        if context_name:
            queryset = queryset.filter(contexts__name__icontains=context_name)

        return queryset

    # FUTURE USE: Resource Upload Handling
    def perform_create(self, serializer):
        # You can add logic here to handle file processing or 
        # auto-assigning contexts based on the node
        serializer.save()

class KnowledgeNodeViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeNodeSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        # Base queryset with annotations
        base_qs = KnowledgeNode.objects.annotate(resource_count=Count('resources'))

        # FIX: Only filter for roots if we are LISTING (GET /nodes/)
        # and not asking for 'all'.
        # This allows 'retrieve', 'update', and 'destroy' to find child nodes by ID.
        if self.action == 'list':
            if self.request.query_params.get('all', 'false').lower() == 'true':
                return base_qs
            return base_qs.filter(parent__isnull=True)
        
        # For individual node actions (ID 14 etc), return everything
        return base_qs

    # FUTURE USE: Bulk toggle status or Reordering
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def toggle_status(self, request, pk=None):
        node = self.get_object()
        node.is_active = not node.is_active
        node.save()
        return Response({'status': 'visibility toggled', 'is_active': node.is_active})

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

class StudentProgressViewSet(viewsets.ModelViewSet):
    serializer_class = StudentProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudentProgress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
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
