from django.contrib import admin
from .models import KnowledgeNode, Resource, ProgramContext

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
