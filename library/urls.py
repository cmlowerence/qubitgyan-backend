from django.urls import include, path

urlpatterns = [
    path('', include('library.api.v1.urls')),
]
