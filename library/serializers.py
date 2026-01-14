import re
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Count 
from .models import KnowledgeNode, Resource, ProgramContext, StudentProgress, UserProfile

class ProgramContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramContext
        fields = ['id', 'name', 'description']

class ResourceSerializer(serializers.ModelSerializer):
    contexts = ProgramContextSerializer(many=True, read_only=True)
    context_ids = serializers.PrimaryKeyRelatedField(
        queryset=ProgramContext.objects.all(), write_only=True, many=True, source='contexts'
    )
    
    node_name = serializers.ReadOnlyField(source='node.name')
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
        if obj.children.exists():
            children_qs = obj.children.all().annotate(
                resource_count=Count('resources', distinct=True),
                items_count=Count('children', distinct=True)
            )
            return ChildNodeSerializer(children_qs, many=True).data
        return []

class UserSerializer(serializers.ModelSerializer):
    # CHANGED: Use MethodFields for safety. 
    # This prevents the 500 Error if the UserProfile is missing.
    created_by = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    is_suspended = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'is_staff', 'is_superuser', 'password',
            'created_by', 'avatar_url', 'is_suspended'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    # --- SAFE GETTERS ---
    def get_created_by(self, obj):
        try:
            return obj.profile.created_by.username if obj.profile.created_by else None
        except UserProfile.DoesNotExist:
            return None

    def get_avatar_url(self, obj):
        try:
            return obj.profile.avatar_url
        except UserProfile.DoesNotExist:
            return None

    def get_is_suspended(self, obj):
        try:
            return obj.profile.is_suspended
        except UserProfile.DoesNotExist:
            return False
    # --------------------

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        user = User.objects.create_user(**validated_data)
        # Create profile safely
        UserProfile.objects.create(user=user, **profile_data)
        return user

    def update(self, instance, validated_data):
        # We manually check for 'profile' in the initial data because 
        # MethodFields are read-only by default
        profile_data = self.initial_data.get('profile', {})
        
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        instance.save()

        # Update or Create Profile
        if profile_data:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            if 'avatar_url' in profile_data:
                profile.avatar_url = profile_data['avatar_url']
            if 'is_suspended' in profile_data:
                profile.is_suspended = profile_data['is_suspended']
            profile.save()
            
        return instance

class StudentProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProgress
        fields = ['id', 'resource', 'is_completed', 'last_accessed']
        read_only_fields = ['user']
