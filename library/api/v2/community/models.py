# qubitgyan-backend\library\api\v2\community\models.py


import uuid
from django.db import models
from django.conf import settings
from library.models import KnowledgeNode
from django.utils import timezone

class Post(models.Model):
    TYPE_CHOICES = [
        ('DOUBT', 'Question / Doubt'),
        ('RESOURCE', 'Study Material'),
        ('DISCUSSION', 'General Discussion'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='community_posts')
    topic = models.ForeignKey(KnowledgeNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='community_posts')
    
    post_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='DOUBT')
    title = models.CharField(max_length=255)
    content = models.TextField(help_text="Supports Markdown and LaTeX for math formulas.")
    
    upvote_score = models.IntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False, help_text="If True, no new comments can be added.")
    is_deleted = models.BooleanField(default=False, help_text="Soft deletion to preserve community knowledge.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_deleted', '-created_at']),
            models.Index(fields=['is_deleted', '-upvote_score']),
            models.Index(fields=['post_type', 'is_deleted']),
            # THE FIX: Lightning-fast topic filtering
            models.Index(fields=['topic', 'is_deleted', '-created_at']), 
        ]
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title[:50]


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='community_comments')
    
    content = models.TextField(help_text="Supports Markdown and LaTeX.")
    
    upvote_score = models.IntegerField(default=0)
    is_accepted_answer = models.BooleanField(default=False)
    
    is_deleted = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['post', 'is_deleted', 'created_at']),
            models.Index(fields=['post', '-is_accepted_answer', 'created_at']),
        ]
        ordering = ['-is_accepted_answer', 'created_at']

    def __str__(self):
        return f"Comment by {self.author_id} on {self.post_id}"


class Vote(models.Model):
    VOTE_CHOICES = [
        (1, 'Upvote'),
        (-1, 'Downvote'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='votes')
    
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')
    
    value = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True,)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_user_post_vote'),
            models.UniqueConstraint(fields=['user', 'comment'], name='unique_user_comment_vote'),
            
            models.CheckConstraint(
                condition=(
                    models.Q(post__isnull=False, comment__isnull=True) |
                    models.Q(post__isnull=True, comment__isnull=False)
                ),
                name='vote_must_be_strictly_post_or_comment'
            )
        ]
