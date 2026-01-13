from django.contrib import admin
from django.urls import path, include
# Import JWT views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This points to the file above - now including Global Search
    path('api/v1/', include('library.urls')), 
    
    # AUTHENTICATION ENDPOINTS (PRESERVED)
    # Login (Send Username/Password -> Get Token):
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # Refresh (Get new token when old one expires):
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Keep this for the browsable API to work nicely
    path('api-auth/', include('rest_framework.urls')),
]
