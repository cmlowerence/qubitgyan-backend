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
    pagination_class = None

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all().order_by('order')
    serializer_class = ResourceSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'contexts__name', 'node__name']

    def get_queryset(self):
        queryset = Resource.objects.all()
        
        # Filter by specific folder
        node_id = self.request.query_params.get('node', None)
        if node_id:
            queryset = queryset.filter(node_id=node_id).order_by('order')
            return queryset

        # Global Filters
        r_type = self.request.query_params.get('type', None)
        if r_type and r_type != 'ALL':
            queryset = queryset.filter(resource_type=r_type)

        context_id = self.request.query_params.get('context', None)
        if context_id and context_id != 'ALL':
            queryset = queryset.filter(contexts__id=context_id)

        return queryset.order_by('-created_at')

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reorder(self, request):
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

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Prevent deletion of Superuser
        if instance.is_superuser:
            return Response(
                {"error": "Action Forbidden: Cannot delete the Superuser account."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

class StudentProgressViewSet(viewsets.ModelViewSet):
    serializer_class = StudentProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudentProgress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def all_admin_view(self, request):
        progress = StudentProgress.objects.all().select_related('user', 'resource')
        data = []
        for p in progress:
            data.append({
                "id": p.id,
                "user_details": {
                    "username": p.user.username, 
                    "email": p.user.email
                },
                "resource_details": {
                    "title": p.resource.title, 
                    "resource_type": p.resource.resource_type
                },
                "is_completed": p.is_completed,
                "last_accessed": p.last_accessed
            })
        return Response(data)

class GlobalSearchView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response({"results": []})

        results = []

        # 1. Search Knowledge Nodes
        nodes = KnowledgeNode.objects.filter(name__icontains=query)[:5]
        for n in nodes:
            results.append({
                "type": "NODE",
                "id": n.id,
                "title": n.name,
                "subtitle": f"Type: {n.node_type}",
                "url": f"/admin/tree/{n.id}"
            })

        # 2. Search Resources
        resources = Resource.objects.filter(title__icontains=query)[:5]
        for r in resources:
            results.append({
                "type": "RESOURCE",
                "id": r.id,
                "title": r.title,
                "subtitle": f"File: {r.resource_type}",
                "url": f"/admin/tree/{r.node}"
            })

        # 3. Search Users
        users = User.objects.filter(username__icontains=query)[:5]
        for u in users:
            results.append({
                "type": "USER",
                "id": u.id,
                "title": u.username,
                "subtitle": u.email,
                "url": "/admin/users"
            })

        return Response(results)

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # 1. Basic Counters (Split Admins/Students)
        total_nodes = KnowledgeNode.objects.count()
        total_resources = Resource.objects.count()
        
        # Separate counts
        total_admins = User.objects.filter(is_staff=True).count()
        total_students = User.objects.filter(is_staff=False).count()

        # 2. Resource Distribution
        type_distribution = Resource.objects.values('resource_type').annotate(count=Count('id'))

        # 3. Subject Leaders
        top_subjects = KnowledgeNode.objects.filter(node_type='TOPIC') \
            .annotate(resource_count=Count('resources')) \
            .order_by('-resource_count')[:5] \
            .values('name', 'resource_count')

        # 4. Recent Activity
        recent_resources = Resource.objects.all().order_by('-created_at')[:5]
        recent_serialized = ResourceSerializer(recent_resources, many=True).data

        return Response({
            "counts": {
                "nodes": total_nodes,
                "admins": total_admins,    # New Field
                "students": total_students, # New Field
                "resources": total_resources,
            },
            "charts": {
                "distribution": type_distribution,
                "top_subjects": top_subjects
            },
            "recent_activity": recent_serialized
        })
