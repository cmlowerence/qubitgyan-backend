import re
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Count # <--- 1. Added this import
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
    
    # Smart Inputs/Outputs
    google_drive_link = serializers.CharField(write_only=True, required=False, allow_blank=True)
    preview_link = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'resource_type', 'node', 
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

# 2. Added Helper Serializer for the children list (Prevents recursion issues)
class ChildNodeSerializer(serializers.ModelSerializer):
    resource_count = serializers.IntegerField(read_only=True)
    # Optional: If you want to show "Items" count too, uncomment the next line and the annotation below
    # children_count = serializers.IntegerField(source='children.count', read_only=True)

    class Meta:
        model = KnowledgeNode
        fields = [
            'id', 'name', 'node_type', 'parent', 
            'order', 'thumbnail_url', 'is_active', 
            'resource_count' 
            # We do NOT include 'children' here to keep the list flat and fast
        ]

class KnowledgeNodeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    resource_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = KnowledgeNode
        fields = [
            'id', 'name', 'node_type', 'parent', 
            'order', 'thumbnail_url', 'is_active', 
            'children', 'resource_count'
        ]

    def get_children(self, obj):
        """
        Manually fetch children AND annotate them with resource_count.
        This fixes the '0 Resources' bug on the folder cards.
        """
        if obj.children.exists():
            # Force the annotation: Count resources for EACH child
            children_qs = obj.children.all().annotate(resource_count=Count('resources'))
            return ChildNodeSerializer(children_qs, many=True).data
        return []

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        # Secure password hashing
        return User.objects.create_user(**validated_data)

class StudentProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProgress
        fields = ['id', 'resource', 'is_completed', 'last_accessed']
        read_only_fields = ['user']
