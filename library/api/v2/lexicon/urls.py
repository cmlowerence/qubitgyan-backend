from django.urls import path
from .views.public import WordSearchView, DailyPracticeSetView, WordOfTheDayView, TrendingWordsView
from .views.manager import (
    WordManagerView, 
    CategoryListCreateView, 
    AssignWordToCategoryView,
    ManualWordOfTheDayView,
    WordListView,
    WordSubEntityMixinView,
)

urlpatterns = [
    # Public (Student) Endpoints
    path('public/search/', WordSearchView.as_view(), name='lexicon-public-search'),
    path('public/daily-practice/', DailyPracticeSetView.as_view(), name='lexicon-public-daily-practice'),
    path('public/word-of-the-day/', WordOfTheDayView.as_view(), name='lexicon-public-wotd'),
    path('public/trending/', TrendingWordsView.as_view(), name='lexicon-public-trending'),

    # Manager (Admin) Endpoints
    path('manager/words/list/', WordListView.as_view(), name='lexicon-manager-word-list'),
    path('manager/words/', WordManagerView.as_view(), name='lexicon-manager-word-create'),
    path('manager/words/<uuid:pk>/', WordManagerView.as_view(), name='lexicon-manager-word-update'),
    path('manager/words/<uuid:word_id>/add-<str:entity_type>/', WordSubEntityMixinView.as_view(), name='lexicon-manager-add-entity'),
    
    path('manager/categories/', CategoryListCreateView.as_view(), name='lexicon-manager-categories'),
    path('manager/words/<uuid:word_id>/categories/<uuid:category_id>/', AssignWordToCategoryView.as_view(), name='lexicon-manager-assign-category'),
    path('manager/word-of-the-day/override/', ManualWordOfTheDayView.as_view(), name='lexicon-manager-wotd-override'),
]