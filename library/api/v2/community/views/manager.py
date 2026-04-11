# qubitgyan-backend\library\api\v2\community\views\manager.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest

from ..models import Post, Comment

class PostModerationView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        update_fields = ['updated_at']
        
        new_is_deleted = request.data.get('is_deleted', post.is_deleted)
        new_is_pinned = request.data.get('is_pinned', post.is_pinned)
        new_is_locked = request.data.get('is_locked', post.is_locked)

        if new_is_deleted:
            new_is_pinned = False

        if post.is_deleted != new_is_deleted:
            post.is_deleted = new_is_deleted
            update_fields.append('is_deleted')
        
        if post.is_pinned != new_is_pinned:
            post.is_pinned = new_is_pinned
            update_fields.append('is_pinned')

        if post.is_locked != new_is_locked:
            post.is_locked = new_is_locked
            update_fields.append('is_locked')

        if len(update_fields) > 1:
            post.save(update_fields=update_fields)
            
        return Response({"message": "Post updated.", "state": new_is_deleted}, status=status.HTTP_200_OK)


class CommentModerationView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        update_fields = ['updated_at']
        
        new_is_deleted = request.data.get('is_deleted', comment.is_deleted)
        new_is_accepted = request.data.get('is_accepted_answer', comment.is_accepted_answer)

        if new_is_deleted:
            new_is_accepted = False

        with transaction.atomic():
            if new_is_accepted and not comment.is_accepted_answer:
                Comment.objects.filter(post=comment.post, is_accepted_answer=True).update(is_accepted_answer=False)

            if comment.is_deleted != new_is_deleted:
                count_delta = -1 if new_is_deleted else 1
                Post.objects.filter(id=comment.post_id).update(
                    comment_count=Greatest(F('comment_count') + count_delta, Value(0))
                )

            comment.is_deleted = new_is_deleted
            comment.is_accepted_answer = new_is_accepted
            
            comment.save(update_fields=['is_deleted', 'is_accepted_answer', 'updated_at'])

        return Response({"message": "Comment updated."}, status=status.HTTP_200_OK)
