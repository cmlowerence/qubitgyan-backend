from django.contrib import admin
from .models import KnowledgeNode, Resource, ProgramContext
from .models import AdmissionRequest, Quiz, Question, Option, AdminAuditLog

@admin.register(AdmissionRequest)
class AdmissionRequestAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'email', 'status', 'created_at')
    list_filter = ('status',)

admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Option)
admin.site.register(AdminAuditLog)

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
