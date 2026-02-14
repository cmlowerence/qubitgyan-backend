from django.contrib import admin
from .models import (
    KnowledgeNode, Resource, ProgramContext, UserProfile,
    AdmissionRequest, Quiz, Question, Option, AdminAuditLog,
    Course, Enrollment, Notification, UserNotificationStatus, 
    QueuedEmail, UploadedImage
)

# --- Original Core Models ---
@admin.register(ProgramContext)
class ProgramContextAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')

@admin.register(KnowledgeNode)
class KnowledgeNodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'node_type', 'parent', 'order')
    list_filter = ('node_type',)
    search_fields = ('name',)
    ordering = ('node_type', 'order')

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'resource_type', 'node')
    list_filter = ('resource_type', 'contexts')
    search_fields = ('title', 'google_drive_id')
    autocomplete_fields = ['node']

# --- User & Gamification Profiles ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_streak', 'total_learning_minutes', 'can_manage_content')
    search_fields = ('user__username', 'user__email')

# --- Admissions & Auditing ---
@admin.register(AdmissionRequest)
class AdmissionRequestAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'email', 'status', 'created_at')
    list_filter = ('status',)

admin.site.register(AdminAuditLog)

# --- Quizzes ---
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Option)

# --- Courses & Enrollments ---
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published',)

admin.site.register(Enrollment)

# --- Notifications & Emails ---
admin.site.register(Notification)
admin.site.register(UserNotificationStatus)

@admin.register(QueuedEmail)
class QueuedEmailAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'subject', 'is_sent', 'created_at')
    list_filter = ('is_sent',)

@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'file_size_bytes', 'uploaded_at')
    list_filter = ('category',)
    search_fields = ('name',)

