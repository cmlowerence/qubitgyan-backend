# qubitgyan-backend\library\api\v2\community\urls.py
from django.urls import path
from .views.public import PostListView, PostDetailView, CommentCreateView, VoteActionView
from .views.manager import PostModerationView, CommentModerationView

urlpatterns = [
    path('posts/', PostListView.as_view(), name='community-post-list'),
    path('posts/<uuid:post_id>/', PostDetailView.as_view(), name='community-post-detail'),
    path('posts/<uuid:post_id>/comments/', CommentCreateView.as_view(), name='community-comment-create'),
    path('vote/', VoteActionView.as_view(), name='community-vote-action'),

    path('manager/posts/<uuid:post_id>/', PostModerationView.as_view(), name='community-manager-post'),
    path('manager/comments/<uuid:comment_id>/', CommentModerationView.as_view(), name='community-manager-comment'),
]