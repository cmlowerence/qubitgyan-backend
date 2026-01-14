import re
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Count 
from .models import KnowledgeNode, Resource, ProgramContext, StudentProgress

class ProgramContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramContext
        fields = ['id', 'name', 'description']

class ResourceSerializer(serializers.ModelSerializer):
    contexts = ProgramContextSerializer(many=True, read_only=True)
    context_ids = serializers.PrimaryKeyRelatedField(
        queryset=ProgramContext.objects.all(), write_only=True, many=True, source='contexts'
    )
    
    # Fetch parent folder name safely
    node_name = serializers.ReadOnlyField(source='node.name')

    # Smart Inputs/Outputs
    google_drive_link = serializers.CharField(write_only=True, required=False, allow_blank=True)
    preview_link = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'resource_type', 
            'node', 'node_name', 
            'contexts', 'context_ids', 
            'google_drive_id', 'google_drive_link',
            'external_url', 'content_text', 
            'preview_link', 'created_at', 'order'
        ]

    def validate(self, attrs):
        # Extract ID from pasted Google Drive Link
        drive_link = attrs.pop('google_drive_link', None)
        if drive_link:
            match = re.search(r'[-\w]{25,}', drive_link)
            attrs['google_drive_id'] = match.group() if match else drive_link
        return attrs

    def get_preview_link(self, obj):
        if obj.resource_type == 'PDF' and obj.google_drive_id:
            return f"https://drive.google.com/file/d/{obj.google_drive_id}/preview"
        if obj.resource_type == 'VIDEO' and obj.external_url:
            return obj.external_url
        return None

class ChildNodeSerializer(serializers.ModelSerializer):
    resource_count = serializers.IntegerField(read_only=True)
    items_count = serializers.IntegerField(read_only=True) 

    class Meta:
        model = KnowledgeNode
        fields = [
            'id', 'name', 'node_type', 'parent', 
            'order', 'thumbnail_url', 'is_active', 
            'resource_count',
            'items_count'
        ]

class KnowledgeNodeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    resource_count = serializers.IntegerField(read_only=True, required=False)
    items_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = KnowledgeNode
        fields = [
            'id', 'name', 'node_type', 'parent', 
            'order', 'thumbnail_url', 'is_active', 
            'children', 'resource_count', 'items_count'
        ]

    def get_children(self, obj):
        """
        Fetch children and annotate with BOTH resource_count and items_count.
        distinct=True is required to prevent multiplication errors when counting two relations.
        """
        if obj.children.exists():
            children_qs = obj.children.all().annotate(
                resource_count=Count('resources', distinct=True),
                items_count=Count('children', distinct=True)
            )
            return ChildNodeSerializer(children_qs, many=True).data
        return []

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # ADDED: 'is_superuser' field so Frontend knows who the Boss is
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        # Secure password hashing
        return User.objects.create_user(**validated_data)

class StudentProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProgress
        fields = ['id', 'resource', 'is_completed', 'last_accessed']
        read_only_fields = ['user']
