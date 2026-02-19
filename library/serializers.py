import re
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Count
from .models import (
    KnowledgeNode, Resource, ProgramContext, 
    StudentProgress, UserProfile, Bookmark, 
    AdmissionRequest, Quiz, Question, Option, 
    QuizAttempt, QuestionResponse, Course, 
    Enrollment, Notification, UserNotificationStatus, 
    UploadedImage)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.cache import cache

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

        # Extract Google Drive ID if link provided
        if drive_link:
            match = re.search(r'[-\w]{25,}', drive_link)
            attrs['google_drive_id'] = match.group() if match else drive_link

        r_type = attrs.get("resource_type") or getattr(self.instance, "resource_type", None)
        drive_id = attrs.get("google_drive_id") or getattr(self.instance, "google_drive_id", None)
        external_url = attrs.get("external_url") or getattr(self.instance, "external_url", None)
        content_text = attrs.get("content_text") or getattr(self.instance, "content_text", None)

        if r_type == "PDF" and not drive_id:
            raise serializers.ValidationError("PDF resources must include a Google Drive file.")

        if r_type == "VIDEO" and not external_url:
            raise serializers.ValidationError("Video resources must include an external video URL.")

        if r_type == "EXERCISE" and not content_text:
            raise serializers.ValidationError("Exercises must include text content.")

        return attrs

    def get_preview_link(self, obj):
        if obj.resource_type == 'PDF' and obj.google_drive_id:
            return f"https://drive.google.com/file/d/{obj.google_drive_id}/preview"
        if obj.resource_type == 'VIDEO' and obj.external_url:
            return obj.external_url
        return None

class ChildNodeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    resource_count = serializers.IntegerField(read_only=True)
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = KnowledgeNode
        fields = [
            'id',
            'name',
            'node_type',
            'parent',
            'order',
            'thumbnail_url',
            'is_active',
            'children',
            'resource_count',
            'items_count',
        ]

    def get_children(self, obj):
        request = self.context.get("request")

        # Default depth = 10 (full tree)
        depth = 10
        if request:
            try:
                depth = int(request.query_params.get("depth", 10))
            except ValueError:
                depth = 10

        # Stop recursion
        if depth <= 0:
            return []

        # Reduce depth for next level
        self.context["request"].query_params._mutable = True
        self.context["request"].query_params["depth"] = str(depth - 1)
        self.context["request"].query_params._mutable = False

        children_qs = obj.children.all()

        serializer = ChildNodeSerializer(
            children_qs,
            many=True,
            context=self.context
        )

        return serializer.data

class KnowledgeNodeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    resource_count = serializers.IntegerField(read_only=True)
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = KnowledgeNode
        fields = [
            'id',
            'name',
            'node_type',
            'parent',
            'order',
            'thumbnail_url',
            'is_active',
            'children',
            'resource_count',
            'items_count',
        ]

    def get_children(self, obj):
        request = self.context.get("request")

        depth = 10
        if request:
            try:
                depth = int(request.query_params.get("depth", 10))
            except ValueError:
                depth = 10

        if depth <= 0:
            return []

        # Reduce depth
        self.context["request"].query_params._mutable = True
        self.context["request"].query_params["depth"] = str(depth - 1)
        self.context["request"].query_params._mutable = False

        children_qs = obj.children.all()

        serializer = ChildNodeSerializer(
            children_qs,
            many=True,
            context=self.context
        )

        return serializer.data


class UserProfileInputSerializer(serializers.Serializer):
    avatar_url = serializers.URLField(required=False, allow_blank=True)
    is_suspended = serializers.BooleanField(required=False)


class UserSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    is_suspended = serializers.SerializerMethodField()

    # Permission flags (read-only) propagated from UserProfile
    can_approve_admissions = serializers.SerializerMethodField()
    can_manage_content = serializers.SerializerMethodField()
    can_manage_users = serializers.SerializerMethodField()

    # Accept a write-only `profile` object in incoming payloads (nested serializer)
    profile = UserProfileInputSerializer(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_staff', 'is_superuser', 'password',
            'created_by', 'avatar_url', 'is_suspended',
            'can_approve_admissions', 'can_manage_content', 'can_manage_users',
            'profile'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def get_created_by(self, obj):
        if hasattr(obj, 'profile') and obj.profile.created_by:
            return obj.profile.created_by.username
        return None

    def get_avatar_url(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.avatar_url
        return None

    def get_is_suspended(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.is_suspended
        return False

    def get_can_approve_admissions(self, obj):
        if hasattr(obj, 'profile'):
            return bool(obj.profile.can_approve_admissions)
        return False

    def get_can_manage_content(self, obj):
        if hasattr(obj, 'profile'):
            return bool(obj.profile.can_manage_content)
        return False

    def get_can_manage_users(self, obj):
        if hasattr(obj, 'profile'):
            return bool(obj.profile.can_manage_users)
        return False

    def create(self, validated_data):
        # Prefer validated nested `profile`, but accept legacy top-level `avatar_url` if present
        profile_data = validated_data.pop('profile', {}) or {}
        if not profile_data and 'avatar_url' in self.initial_data:
            profile_data = {'avatar_url': self.initial_data.get('avatar_url')}

        user = User.objects.create_user(**validated_data)
        UserProfile.objects.create(user=user, **profile_data)
        return user

    def update(self, instance, validated_data):
        # Prefer validated nested `profile` from payload; fall back to initial_data (legacy)
        profile_data = validated_data.pop('profile', None)
        if profile_data is None:
            profile_data = self.initial_data.get('profile', {}) or {}

        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        instance.save()

        # Also accept legacy top-level `avatar_url` in request body
        if not profile_data and 'avatar_url' in self.initial_data:
            profile_data = {'avatar_url': self.initial_data.get('avatar_url')}

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

class AdmissionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdmissionRequest
        fields = ['id', 'student_name', 'email', 'phone', 'class_grade', 'learning_goal', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']

class AdminAdmissionApprovalSerializer(serializers.ModelSerializer):
    """Used by Admins to approve/reject"""
    class Meta:
        model = AdmissionRequest
        fields = ['status', 'review_remarks']

class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']
        # Note: is_correct should be stripped out dynamically for Student views to prevent cheating

class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = ['id', 'text', 'image_url', 'marks_positive', 'marks_negative', 'order', 'options']

class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    resource_title = serializers.ReadOnlyField(source='resource.title')

    class Meta:
        model = Quiz
        fields = ['id', 'resource', 'resource_title', 'passing_score_percentage', 'time_limit_minutes', 'questions']

class StudentOptionSerializer(serializers.ModelSerializer):
    """Strips out the 'is_correct' field so students can't cheat"""
    class Meta:
        model = Option
        fields = ['id', 'text'] 



class StudentQuizReadSerializer(serializers.ModelSerializer):
    questions = StudentQuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Quiz
        fields = ['id', 'passing_score_percentage', 'time_limit_minutes', 'questions']

class QuestionResponseSerializer(serializers.ModelSerializer):
    """Shows the student what they picked and if it was correct"""
    question_text = serializers.ReadOnlyField(source='question.text')
    selected_option_text = serializers.ReadOnlyField(source='selected_option.text')
    is_correct = serializers.ReadOnlyField(source='selected_option.is_correct')

    class Meta:
        model = QuestionResponse
        fields = ['id', 'question', 'question_text', 'selected_option', 'selected_option_text', 'is_correct']

class QuizAttemptSerializer(serializers.ModelSerializer):
    """Shows the overall score and includes all the individual responses"""
    responses = QuestionResponseSerializer(many=True, read_only=True)
    quiz_title = serializers.ReadOnlyField(source='quiz.resource.title')

    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'quiz_title', 'start_time', 'end_time', 'total_score', 'is_completed', 'responses']

class CourseSerializer(serializers.ModelSerializer):
    """Used for browsind available courses"""
    root_node_name = serializers.ReadOnlyField(source='root_node.name')
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'thumbnail_url', 'is_published', 'root_node_name', 'created_at', 'is_enrolled']

    def get_is_enrolled(self, obj):
        user = self.context.get('request').user if self.context and 'request' in self.context else None
        if user and user.is_authenticated:
            return Enrollment.objects.filter(user=user, course=obj).exists()
        return False

class EnrollmentSerializer(serializers.ModelSerializer):
    course_details = CourseSerializer(source='course', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'course', 'course_details', 'enrolled_at']
        read_only_fields = ['user']

class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'created_at', 'is_read']

    def get_is_read(self, obj):
        # Uses prefetched cache instead of DB query
        statuses = getattr(obj, 'current_user_statuses', [])
        if statuses:
            return statuses[0].is_read
        return False
    
    
    
class ChangePasswordSerializer(serializers.Serializer):
    """Securely handles password changes for authenticated users"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        # This checks against the validators in your settings.py 
        # (e.g., MinimumLengthValidator, CommonPasswordValidator)
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

class MyProfileSerializer(serializers.ModelSerializer):
    """Sends the student's gamification stats and basic info to their dashboard"""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'username', 'email', 'first_name', 'avatar_url', 
            'current_streak', 'longest_streak', 'total_learning_minutes', 'last_active_date'
        ]

class BookmarkSerializer(serializers.ModelSerializer):
    """Provides the bookmark ID and details about the saved resource"""
    resource_title = serializers.ReadOnlyField(source='resource.title')
    resource_type = serializers.ReadOnlyField(source='resource.resource_type')

    class Meta:
        model = Bookmark
        fields = ['id', 'resource', 'resource_title', 'resource_type', 'created_at']
        read_only_fields = ['user']

class UploadedImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedImage
        fields = '__all__'

