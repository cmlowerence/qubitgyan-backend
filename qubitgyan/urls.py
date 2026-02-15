from django.contrib import admin
from django.urls import path, include
# Import JWT views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('stark-tower/qubitgyan/administration/', admin.site.urls),
    path('api/v1/', include('library.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api-auth/', include('rest_framework.urls')),
]
