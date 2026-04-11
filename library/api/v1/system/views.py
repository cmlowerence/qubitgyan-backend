from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache

class HealthCheckView(APIView):

    permission_classes = []

    def get(self, request):

        # DB Check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_status = "ok"
        except Exception:
            db_status = "error"

        # Cache Check
        try:
            cache.set("health_check", "ok", 5)
            cache_status = cache.get("health_check")
        except Exception:
            cache_status = "error"

        return Response({
            "status": "healthy",
            "database": db_status,
            "cache": cache_status,
        })