from django.contrib import admin
from .models import (
    UserProfile, ProgramContext, KnowledgeNode, Resource, StudentProgress,
    AdmissionRequest, AdminAuditLog, Quiz, Question, Option, QuizAttempt,
    QuestionResponse, QueuedEmail, Course, Enrollment, Notification,
    UserNotificationStatus, Bookmark, UploadedImage
)


class OptionInline(admin.TabularInline):
    model = Option
    extra = 1


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "current_streak", "total_learning_minutes", "is_suspended", "can_manage_content")
    list_filter = ("is_suspended", "can_manage_content", "can_approve_admissions")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("last_active_date", "total_learning_minutes")


@admin.register(ProgramContext)
class ProgramContextAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(KnowledgeNode)
class KnowledgeNodeAdmin(admin.ModelAdmin):
    list_display = ("name", "node_type", "parent", "order", "is_active")
    list_filter = ("node_type", "is_active")
    search_fields = ("name", "description")
    ordering = ("node_type", "order")


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "resource_type", "node", "is_active", "is_archived", "order")
    list_filter = ("resource_type", "is_active", "is_archived")
    search_fields = ("title", "node__name")
    filter_horizontal = ("contexts",)
    ordering = ("node", "order")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title", "description")


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("resource", "passing_score_percentage", "time_limit_minutes")
    search_fields = ("resource__title",)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "quiz", "marks_positive", "marks_negative", "order")
    list_filter = ("quiz",)
    search_fields = ("text", "quiz__resource__title")
    inlines = [OptionInline]
    ordering = ("quiz", "order")



@admin.register(StudentProgress)
class StudentProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "resource", "is_completed", "time_spent_seconds", "last_accessed")
    list_filter = ("is_completed",)
    search_fields = ("user__username", "resource__title")


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "quiz", "total_score", "is_completed", "start_time")
    list_filter = ("is_completed",)
    search_fields = ("user__username", "quiz__resource__title")


@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "selected_option")
    search_fields = ("attempt__user__username", "question__text")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "enrolled_at")
    list_filter = ("course",)
    search_fields = ("user__username", "course__title")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "resource", "created_at")
    search_fields = ("user__username", "resource__title")


@admin.register(AdmissionRequest)
class AdmissionRequestAdmin(admin.ModelAdmin):
    list_display = ("student_first_name", "student_last_name", "email", "status", "created_at")
    list_filter = ("status", "preferred_mode")
    search_fields = ("email", "student_first_name", "student_last_name", "phone")


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("admin_user", "action", "ip_address", "timestamp")
    list_filter = ("timestamp", "admin_user")
    search_fields = ("action", "admin_user__username")
    
    # Audit logs should be read-only for security purposes
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(QueuedEmail)
class QueuedEmailAdmin(admin.ModelAdmin):
    list_display = ("recipient_email", "subject", "is_sent", "retry_count", "created_at")
    list_filter = ("is_sent",)
    search_fields = ("recipient_email", "subject")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "sender", "target_user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "message")


@admin.register(UserNotificationStatus)
class UserNotificationStatusAdmin(admin.ModelAdmin):
    list_display = ("user", "notification", "is_read", "read_at")
    list_filter = ("is_read",)
    search_fields = ("user__username", "notification__title")


@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "file_size_bytes", "uploaded_by", "uploaded_at")
    list_filter = ("category",)
    search_fields = ("name", "supabase_path", "uploaded_by__username")
    readonly_fields = ("file_size_bytes", "uploaded_at", "supabase_path", "public_url")

