from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class UserProfile(models.Model):
    """
    Extension of the User model to store extra metadata.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Who made this account? (For Admins to track)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    
    # Custom Avatar (URL for now to keep it simple without media storage setup)
    avatar_url = models.URLField(blank=True, null=True, help_text="Link to profile picture")
    
    # Account Status
    is_suspended = models.BooleanField(default=False, help_text="If true, user cannot log in")

    def __str__(self):
        return f"Profile for {self.user.username}"

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



# ==========================================
# 1. ADMISSION PORTAL & SECURITY
# ==========================================

class AdmissionRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    student_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    class_grade = models.CharField(max_length=50)
    learning_goal = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Audit Trail for Approvals
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_admissions')
    review_remarks = models.TextField(blank=True, null=True, help_text="Notes from the admin who processed this")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student_name} - {self.status}"

class AdminAuditLog(models.Model):
    """Tracks critical admin actions for security and accountability."""
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255) # e.g., "Approved Admission Request for john@example.com"
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']


# ==========================================
# 2. QUIZ ENGINE
# ==========================================

class Quiz(models.Model):
    """Links directly to an existing Resource of type 'QUIZ'"""
    resource = models.OneToOneField('Resource', on_delete=models.CASCADE, related_name='quiz_details')
    passing_score_percentage = models.PositiveIntegerField(default=50)
    time_limit_minutes = models.PositiveIntegerField(default=30, help_text="0 means unlimited time")
    
    def __str__(self):
        return f"Quiz Details for: {self.resource.title}"

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    
    # Media Support (For Supabase S3 / Cloudinary later)
    image_url = models.URLField(blank=True, null=True, help_text="Optional diagram or image for the question")
    
    marks_positive = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    marks_negative = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Penalty for wrong answer (e.g. 0.25)")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q: {self.text[:50]}..."

class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Wrong'})"

class QuizAttempt(models.Model):
    """Tracks a student taking a quiz."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    total_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_completed = models.BooleanField(default=False)

class QuestionResponse(models.Model):
    """Tracks which option a student selected for a specific question."""
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ('attempt', 'question')