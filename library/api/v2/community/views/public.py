# qubitgyan-backend\library\api\v2\community\views\public.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from django.db.models import F, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from django.db import transaction

from library.models import KnowledgeNode
from ..models import Post, Comment, Vote
from ..serializers import PostSerializer, CommentSerializer

class PostListView(APIView):
    """Fetches the main Community Feed with zero N+1 queries."""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        topic_id = request.query_params.get('topic_id')
        
        posts = Post.objects.select_related('author', 'topic').filter(is_deleted=False)
        
        if topic_id:
            posts = posts.filter(topic_id=topic_id)
            
        if request.user.is_authenticated:
            user_vote_subquery = Vote.objects.filter(
                post=OuterRef('pk'), 
                user=request.user
            ).values('value')[:1]
            
            posts = posts.annotate(
                user_vote=Coalesce(Subquery(user_vote_subquery, output_field=IntegerField()), 0)
            )
            
        posts = posts.order_by('-is_pinned', '-created_at')[:50]
        
        return Response(PostSerializer(posts, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        """Creates a new Post."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
            
        serializer = PostSerializer(data=request.data)
        if serializer.is_valid():
            topic_id = request.data.get('topic_id')
            topic = KnowledgeNode.objects.filter(id=topic_id).first() if topic_id else None
            
            serializer.save(author=request.user, topic=topic)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostDetailView(APIView):
    """Fetches a single post, its comments, and safely increments the view count."""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, post_id):
        post = get_object_or_404(Post.objects.select_related('author', 'topic'), id=post_id, is_deleted=False)
        
        Post.objects.filter(id=post.id).update(view_count=F('view_count') + 1)
        post.view_count += 1 
        
        comments = Comment.objects.select_related('author').filter(post=post)[:100]
        
        if request.user.is_authenticated:
            user_post_vote = Vote.objects.filter(post=post, user=request.user).values_list('value', flat=True).first()
            post.user_vote = user_post_vote if user_post_vote else 0
            
            user_comment_vote_sq = Vote.objects.filter(
                comment=OuterRef('pk'), 
                user=request.user
            ).values('value')[:1]
            
            comments = comments.annotate(
                user_vote=Coalesce(Subquery(user_comment_vote_sq, output_field=IntegerField()), 0)
            )
            
        return Response({
            "post": PostSerializer(post).data,
            "comments": CommentSerializer(comments, many=True).data
        }, status=status.HTTP_200_OK)


class CommentCreateView(APIView):
    """Adds a reply to a post and atomically syncs the post's comment_count."""
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id, is_deleted=False, is_locked=False)
        
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                serializer.save(author=request.user, post=post)
                Post.objects.filter(id=post.id).update(comment_count=F('comment_count') + 1)
                
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VoteActionView(APIView):
    """The ultra-secure, highly concurrent Gamification Engine."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        entity_type = request.data.get('type') 
        entity_id = request.data.get('id')
        vote_value = request.data.get('value') 
        
        if entity_type not in ['post', 'comment'] or vote_value not in [1, -1]:
            return Response({"error": "Invalid payload."}, status=status.HTTP_400_BAD_REQUEST)

        ModelClass = Post if entity_type == 'post' else Comment
        filter_kwargs = {entity_type: entity_id, 'user': request.user}

        with transaction.atomic():
            entity = get_object_or_404(ModelClass, id=entity_id, is_deleted=False)
            
            if entity_type == 'post' and entity.is_locked:
                return Response({"error": "This post is locked."}, status=status.HTTP_403_FORBIDDEN)

            existing_vote = Vote.objects.filter(**filter_kwargs).first()
            score_change = 0
            
            if existing_vote:
                if existing_vote.value == vote_value:
                    existing_vote.delete()
                    score_change = -vote_value 
                else:
                    existing_vote.value = vote_value
                    existing_vote.save(update_fields=['value'])
                    score_change = vote_value * 2 
            else:
                Vote.objects.create(value=vote_value, **filter_kwargs)
                score_change = vote_value
                
            if score_change != 0:
                ModelClass.objects.filter(id=entity_id).update(upvote_score=F('upvote_score') + score_change)

        return Response({"status": "Vote recorded.", "score_change": score_change}, status=status.HTTP_200_OK)