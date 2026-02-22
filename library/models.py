from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    avatar_url = models.URLField(blank=True, null=True)
    is_suspended = models.BooleanField(default=False)

    # 🎮 GAMIFICATION (Student Stats)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    total_learning_minutes = models.PositiveIntegerField(default=0)

    # 🛡️ GRANULAR ADMIN PERMISSIONS (Superadmin Control)
    can_approve_admissions = models.BooleanField(default=False)
    can_manage_content = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    
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
        indexes = [
            models.Index(fields=['parent']),
            models.Index(fields=['node_type']),
            models.Index(fields=['order']),
        ]

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
    estimated_time_minutes = models.PositiveIntegerField(default=5, help_text="For gamification and progress tracking")
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False, help_text="Hide from students instead of deleting")

    class Meta:
        indexes = [
            models.Index(fields=['node']),
            models.Index(fields=['resource_type']),
            models.Index(fields=['order']),
            models.Index(fields=['created_at'])
        ]

    def __str__(self):
        return self.title

class StudentProgress(models.Model):
    """Tracks if a student has completed a specific resource"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='progress_records')
    
    is_completed = models.BooleanField(default=False)
    last_accessed = models.DateTimeField(auto_now=True)
    resume_timestamp = models.IntegerField(default=0, help_text="Saved playback time in seconds")
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['resource']),
            models.Index(fields=['user', 'resource']),
            models.Index(fields=['is_completed']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.resource.title}"
    
    @property
    def user_profile(self):
        """Acess to the profile of the student for gamification stats"""
        if hasattr(self.user, 'profile'):
            return self.user.profile
        return None

class AdmissionRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    student_first_name = models.CharField(max_length=100)
    student_last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    class_grade = models.CharField(max_length=50)
    learning_goal = models.TextField(blank=True, null=True)
    guardian_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_phone = models.CharField(max_length=20, blank=True, null=True)
    preferred_mode = models.CharField(max_length=20, default='ONLINE')
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True, help_text="Additional info from the student or admin")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Audit Trail for Approvals
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_admissions')
    review_remarks = models.TextField(blank=True, null=True, help_text="Notes from the admin who processed this")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student_first_name} {self.student_last_name} - {self.status}"

class AdminAuditLog(models.Model):
    """Tracks critical admin actions for security and accountability."""
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255) # e.g., "Approved Admission Request for john@example.com"
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

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
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Wrong'})"

class QuizAttempt(models.Model):
    """Tracks a student taking a quiz."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    total_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_score_possible = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    is_completed = models.BooleanField(default=False)
    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['quiz']),
            models.Index(fields=['user', 'quiz']),
            models.Index(fields=['-start_time']),
        ]

class QuestionResponse(models.Model):
    """Tracks which option a student selected for a specific question."""
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['attempt']),
            models.Index(fields=['question']),
        ]

class QueuedEmail(models.Model):
    """Stores emails safely in the database to prevent Gmail SMTP limits"""
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    html_body = models.TextField(blank=True, null=True)
    is_sent = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"To: {self.recipient_email} - Sent: {self.is_sent}"

class Course(models.Model):
    """The wrapper that holds the learning tree (e.g., TGT Physics Crash Course)"""
    title = models.CharField(max_length=255)
    description = models.TextField()
    thumbnail_url = models.URLField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    
    # Links to the TOP level of your existing KnowledgeNode tree (Domain/Subject)
    root_node = models.OneToOneField('KnowledgeNode', on_delete=models.CASCADE, related_name='course_wrapper')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Enrollment(models.Model):
    """Tracks which courses a student has added to their dashboard"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrolled_students')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['course']),
            models.Index(fields=['user', 'course']),
        ]

class Notification(models.Model):
    """Global or targeted messages from Admins"""
    title = models.CharField(max_length=255)
    message = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    
    # If null, it's a global broadcast. If set, it's for a specific student.
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='targeted_notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['target_user']),
            models.Index(fields=['-created_at']),
        ]
    def __str__(self):
        return f"Notification: {self.title}"

class UserNotificationStatus(models.Model):
    """Tracks the 'Read' status efficiently without duplicating messages"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_statuses')
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['notification']),
            models.Index(fields=['user', 'is_read']),
        ]

class Bookmark(models.Model):
    """Allows students to save specific resources for later"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    resource = models.ForeignKey('Resource', on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['resource']),
            models.Index(fields=['created_at']),
        ]
    def __str__(self):
        return f"{self.user.username} saved {self.resource.title}"
    
class UploadedImage(models.Model):
    """Tracks images uploaded to Supabase to calculate the 1GB limit"""
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, help_text="e.g., 'thumbnails', 'questions', 'avatars'")
    supabase_path = models.CharField(max_length=500, unique=True)
    public_url = models.URLField(max_length=500)
    file_size_bytes = models.BigIntegerField(default=0)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"[{self.category}] {self.name}"

