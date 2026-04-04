
# qubitgyan-backend/library/api/v2/lexicon/urls.py

from django.urls import path

from .interfaces.api.manager_views import (
    AssignWordToCategoryView,
    CategoryDetailView,
    CategoryListCreateView,
    ManualDailyPracticeSetView,
    ManualWordOfTheDayView,
    WordListView,
    WordManagerView,
    WordSubEntityMixinView,
)
from .interfaces.api.public_views import (
    DailyPracticeSetView,
    TrendingWordsView,
    WordOfTheDayView,
    WordSearchView,
)

urlpatterns = [
    path("public/search/", WordSearchView.as_view(), name="lexicon-public-search"),
    path("public/daily-practice/", DailyPracticeSetView.as_view(), name="lexicon-public-daily-practice"),
    path("public/word-of-the-day/", WordOfTheDayView.as_view(), name="lexicon-public-wotd"),
    path("public/trending/", TrendingWordsView.as_view(), name="lexicon-public-trending"),

    path("manager/words/list/", WordListView.as_view(), name="lexicon-manager-word-list"),
    path("manager/words/", WordManagerView.as_view(), name="lexicon-manager-word-create"),
    path("manager/words/<uuid:pk>/", WordManagerView.as_view(), name="lexicon-manager-word-detail"),
    path("manager/words/<uuid:word_id>/add-<str:entity_type>/", WordSubEntityMixinView.as_view(), name="lexicon-manager-add-entity"),
    path("manager/words/<uuid:word_id>/remove-<str:entity_type>/<uuid:entity_id>/", WordSubEntityMixinView.as_view(), name="lexicon-manager-remove-entity"),
    path("manager/categories/", CategoryListCreateView.as_view(), name="lexicon-manager-categories"),
    path("manager/categories/<uuid:pk>/", CategoryDetailView.as_view(), name="lexicon-manager-category-detail"),
    path("manager/words/<uuid:word_id>/categories/<uuid:category_id>/", AssignWordToCategoryView.as_view(), name="lexicon-manager-assign-category"),
    path("manager/word-of-the-day/override/", ManualWordOfTheDayView.as_view(), name="lexicon-manager-wotd-override"),
    path("manager/daily-practice/override/", ManualDailyPracticeSetView.as_view(), name="lexicon-manager-practice-override"),
]
