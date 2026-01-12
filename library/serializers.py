from rest_framework import serializers
from .models import KnowledgeNode, Resource, ProgramContext

# --- 1. Program Context (Tags) ---
class ProgramContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramContext
        fields = ['id', 'name', 'description']

# --- 2. Resources (The Google Drive Logic) ---
class ResourceSerializer(serializers.ModelSerializer):
    contexts = ProgramContextSerializer(many=True, read_only=True)
    context_ids = serializers.PrimaryKeyRelatedField(
        queryset=ProgramContext.objects.all(), write_only=True, many=True, source='contexts'
    )
    
    # NEW: Computed fields for the Frontend
    preview_link = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'resource_type', 'node', 
            'contexts', 'context_ids', 
            'google_drive_id', 'external_url', 'content_text', 
            'preview_link', 'created_at'
        ]

    def get_preview_link(self, obj):
        # Automatically generates a viewable link for the App
        if obj.resource_type == 'PDF' and obj.google_drive_id:
            return f"https://drive.google.com/file/d/{obj.google_drive_id}/preview"
        if obj.resource_type == 'VIDEO' and obj.external_url:
            return obj.external_url
        return None

# --- 3. Knowledge Tree ---
class KnowledgeNodeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    resource_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = KnowledgeNode
        fields = ['id', 'name', 'node_type', 'parent', 'order', 'is_active', 'children', 'resource_count']

    def get_children(self, obj):
        if obj.children.exists():
            return KnowledgeNodeSerializer(obj.children.all(), many=True).data
        return []
