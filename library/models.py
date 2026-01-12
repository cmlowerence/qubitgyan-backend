from django.db import models
from django.contrib.auth.models import User

class ProgramContext(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class KnowledgeNode(models.Model):
    NODE_TYPES = (
        ('DOMAIN', 'Domain'),
        ('SUBJECT', 'Subject'),
        ('SECTION', 'Section'),
        ('TOPIC', 'Topic'),
    )

    name = models.CharField(max_length=255)
    node_type = models.CharField(max_length=20, choices=NODE_TYPES)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    
    # UI Enhancements
    thumbnail_url = models.URLField(blank=True, null=True, help_text="Image URL for the card")
    order = models.PositiveIntegerField(default=0)
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_node_type_display()})"

class Resource(models.Model):
    RESOURCE_TYPES = (
        ('PDF', 'PDF Document'),
        ('VIDEO', 'Video Link'),
        ('QUIZ', 'JSON Quiz'),
        ('EXERCISE', 'Text Exercise'),
    )

    title = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    
    node = models.ForeignKey(KnowledgeNode, on_delete=models.CASCADE, related_name='resources')
    contexts = models.ManyToManyField(ProgramContext, blank=True, related_name='resources')
    
    # Content Links
    google_drive_id = models.CharField(max_length=255, blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    content_text = models.TextField(blank=True, null=True)

    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title

class StudentProgress(models.Model):
    """Tracks if a student has completed a specific resource"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='progress_records')
    
    is_completed = models.BooleanField(default=False)
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'resource')

    def __str__(self):
        return f"{self.user.username} - {self.resource.title}"
