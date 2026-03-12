from django.urls import path, include

urlpatterns = [
    path('lexicon/', include('library.api.v2.lexicon.urls')),
    path('community/', include('library.api.v2.community.urls')),
    path('analytics/', include('library.api.v2.analytics.urls')),
    path('notifications/', include('library.api.v2.notifications.urls')),
    path('spaced-repetition/', include('library.api.v2.spaced_repetition.urls')),
    path('planner/', include('library.api.v2.planner.urls')),
    path('analytics/', include('library.api.v2.analytics.urls')),
]