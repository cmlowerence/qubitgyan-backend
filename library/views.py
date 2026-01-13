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
    queryset = Resource.objects.all().order_class('order')
    serializer_class = ResourceSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'contexts__name']

    def get_queryset(self):
        queryset = Resource.objects.all()
        node_id = self.request.query_params.get('node', None)
        if node_id:
            queryset = queryset.filter(node_id=node_id)
        return queryset.order_by('order')

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reorder(self, request):
        """
        Expects a list of IDs in the new desired order.
        Updates the 'order' field for each resource accordingly.
        """
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
            
        for index, resource_id in enumerate(ids):
            Resource.objects.filter(id=resource_id).update(order=index)
            
        return Response({'status': 'order updated'}, status=status.HTTP_200_OK)

class KnowledgeNodeViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeNodeSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        base_qs = KnowledgeNode.objects.annotate(resource_count=Count('resources'))
        
        # If we are fetching a specific ID (retrieve, update, destroy), 
        # do not filter by parent__isnull to avoid 404s on children.
        if self.action == 'list':
            if self.request.query_params.get('all', 'false').lower() == 'true':
                return base_qs
            return base_qs.filter(parent__isnull=True)
        
        return base_qs

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
