import os

# Define the paths
base_dir = "qubitgyan"
app_name = "library"
models_path = os.path.join(app_name, "models.py")
admin_path = os.path.join(app_name, "admin.py")

# Ensure the app exists before writing
if not os.path.exists(app_name):
    print(f"❌ Error: App folder '{app_name}' not found!")
    print("👉 Please run the 'init_project.py' script from the previous step first.")
    exit()

print("🔨 Writing QubitGyan Database Models...")

# --- 1. CONTENT FOR models.py ---
models_code = """from django.db import models

class ProgramContext(models.Model):
    \"\"\"
    Tags like 'Class 11', 'JEE Mains', 'Olympiad'.
    Allows us to filter content for different goals.
    \"\"\"
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class KnowledgeNode(models.Model):
    \"\"\"
    The Recursive Tree. 
    Examples: 
    - Science (Domain) -> Physics (Subject) -> Thermodynamics (Section)
    \"\"\"
    NODE_TYPES = (
        ('DOMAIN', 'Domain (e.g. Science)'),
        ('SUBJECT', 'Subject (e.g. Physics)'),
        ('SECTION', 'Section (e.g. Thermodynamics)'),
        ('TOPIC', 'Topic (e.g. Entropy)'),
    )

    name = models.CharField(max_length=255)
    node_type = models.CharField(max_length=20, choices=NODE_TYPES)
    
    # The 'self' link allows infinite nesting
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='children'
    )
    
    order = models.PositiveIntegerField(default=0, help_text="Order in the sidebar")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_node_type_display()})"

class Resource(models.Model):
    \"\"\"
    The actual files (PDFs, Videos)
    \"\"\"
    RESOURCE_TYPES = (
        ('PDF', 'PDF Document'),
        ('VIDEO', 'Video Link'),
        ('QUIZ', 'JSON Quiz'),
        ('EXERCISE', 'Text Exercise'),
    )

    title = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    
    # Links
    node = models.ForeignKey(KnowledgeNode, on_delete=models.CASCADE, related_name='resources')
    contexts = models.ManyToManyField(ProgramContext, blank=True, related_name='resources')
    
    # Content
    google_drive_id = models.CharField(max_length=255, blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    content_text = models.TextField(blank=True, null=True, help_text="For Exercises")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
"""

# --- 2. CONTENT FOR admin.py ---
admin_code = """from django.contrib import admin
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
"""

# Write the files
with open(models_path, "w") as f:
    f.write(models_code)
    print(f"✅ Created {models_path}")

with open(admin_path, "w") as f:
    f.write(admin_code)
    print(f"✅ Created {admin_path}")

print("\n🎉 Database structure is ready!")
print("👉 NEXT STEP: Run 'python manage.py makemigrations' and 'python manage.py migrate'")
