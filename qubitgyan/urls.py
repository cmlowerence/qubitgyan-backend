from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('stark-tower/qubitgyan/administration/', admin.site.urls),
    path('api/v1/', include('library.urls')),
    path('api/v2/', include('library.api.v2.urls')),
    path('api/token/', csrf_exempt(TokenObtainPairView.as_view()), name='token_obtain_pair'),
    path('api/token/refresh/', csrf_exempt(TokenRefreshView.as_view()), name='token_refresh'),
    
    path('api-auth/', include('rest_framework.urls')),
]
