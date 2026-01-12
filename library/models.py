from django.db import models

class ProgramContext(models.Model):
    """
    Tags like 'Class 11', 'JEE Mains', 'Olympiad'.
    Allows us to filter content for different goals.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class KnowledgeNode(models.Model):
    """
    The Recursive Tree. 
    Examples: 
    - Science (Domain) -> Physics (Subject) -> Thermodynamics (Section)
    """
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
    """
    The actual files (PDFs, Videos)
    """
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
