# qubitgyan-backend\library\api\v2\community\models.py
from rest_framework import serializers
from .models import Post, Comment

class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'post', 'author', 'author_name', 'content',
            'upvote_score', 'is_accepted_answer', 'is_deleted', 
            'created_at', 'updated_at', 'user_vote'
        ]
        read_only_fields = [
            'id', 'author', 'upvote_score', 'is_accepted_answer', 
            'is_deleted', 'created_at', 'updated_at'
        ]

    def get_author_name(self, obj):
        return obj.author.username if obj.author else "[Deleted User]"

    def get_content(self, obj):
        if obj.is_deleted:
            return "[This comment has been deleted by the user.]"
        return obj.content

    def get_user_vote(self, obj):
        return getattr(obj, 'user_vote', 0)


class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    topic_name = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'author_name', 'topic', 'topic_name', 'post_type',
            'title', 'content', 'upvote_score', 'view_count', 'comment_count',
            'is_pinned', 'is_locked', 'is_deleted', 'created_at', 'updated_at', 'user_vote'
        ]
        read_only_fields = [
            'id', 'author', 'upvote_score', 'view_count', 'comment_count',
            'is_pinned', 'is_locked', 'is_deleted', 'created_at', 'updated_at'
        ]

    def get_author_name(self, obj):
        return obj.author.username if obj.author else "[Deleted User]"

    def get_topic_name(self, obj):
        return obj.topic.name if obj.topic else "General Discussion"

    def get_content(self, obj):
        if obj.is_deleted:
            return "[This post was removed.]"
        return obj.content

    def get_user_vote(self, obj):
        return getattr(obj, 'user_vote', 0)