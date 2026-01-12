from rest_framework import viewsets, filters
from django.db.models import Count
from .models import KnowledgeNode, Resource, ProgramContext
from .serializers import KnowledgeNodeSerializer, ResourceSerializer, ProgramContextSerializer

class ProgramContextViewSet(viewsets.ModelViewSet):
    queryset = ProgramContext.objects.all()
    serializer_class = ProgramContextSerializer

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'contexts__name']

    def get_queryset(self):
        queryset = Resource.objects.all()
        
        # Filter: "Give me all PDFs for Node 5"
        node_id = self.request.query_params.get('node', None)
        if node_id is not None:
            queryset = queryset.filter(node_id=node_id)

        # Filter: "Give me only JEE Mains content"
        context_name = self.request.query_params.get('context', None)
        if context_name is not None:
            queryset = queryset.filter(contexts__name__icontains=context_name)

        return queryset

class KnowledgeNodeViewSet(viewsets.ModelViewSet):
    # Annotate adds a 'resource_count' field automatically
    queryset = KnowledgeNode.objects.annotate(resource_count=Count('resources'))
    serializer_class = KnowledgeNodeSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        # Default: Return Tree Root (Domains)
        # Optional: ?all=true returns Flat List (Good for Search/Dropdowns)
        if self.request.query_params.get('all', 'false').lower() == 'true':
            return KnowledgeNode.objects.all()
            
        return KnowledgeNode.objects.filter(parent__isnull=True)
