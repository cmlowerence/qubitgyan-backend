import os
import time
import uuid
from functools import lru_cache

from supabase import create_client, Client
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Sum
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from library.permissions import (
    IsSuperAdminOnly,
    CanManageContent,
    CanApproveAdmissions,
    CanManageUsers
)

from library.services.email_service import queue_email, send_queued_email

from library.models import (
    AdmissionRequest, UserProfile, AdminAuditLog,
    Quiz, Question, Option, Resource,
    QueuedEmail, UploadedImage
)

from library.serializers import (
    AdmissionRequestSerializer, AdminAdmissionApprovalSerializer,
    QuizSerializer, CourseSerializer, Course,
    NotificationSerializer, Notification,
    UploadedImageSerializer, UserSerializer
)

# ---------------------------------------------------
# Supabase Client Cache (Step-7 Optimization)
# ---------------------------------------------------

@lru_cache(maxsize=1)
def get_supabase_client():
    url = settings.SUPABASE_URL
    key = getattr(settings, 'SUPABASE_SR_KEY', None) or getattr(settings, 'SUPABASE_KEY', None)

    if not url or not key:
        raise ValueError("Supabase configuration missing.")

    return create_client(url, key)


# ---------------------------------------------------
# Image Management ViewSet (Fully Optimized)
# ---------------------------------------------------

class ImageManagementViewSet(viewsets.ModelViewSet):
    """
    Superadmin endpoint for uploading, listing,
    deleting, and browsing images.
    """

    queryset = UploadedImage.objects.all().order_by('-uploaded_at')
    serializer_class = UploadedImageSerializer
    permission_classes = [IsSuperAdminOnly]
    parser_classes = [MultiPartParser, FormParser]

    # ---------------------------------------------------
    # DELETE IMAGE (Safe Delete + Cached Client)
    # ---------------------------------------------------

    def destroy(self, request, *args, **kwargs):
        image_record = self.get_object()

        try:
            supabase = get_supabase_client()

            # Safe delete — ignore storage errors
            try:
                supabase.storage.from_('media').remove(
                    [image_record.supabase_path]
                )
            except Exception:
                pass

            image_record.delete()

            # Invalidate storage cache
            cache.delete("media_storage_status")

            return Response(
                {"message": "Image deleted and storage freed!"},
                status=status.HTTP_204_NO_CONTENT
            )

        except Exception as e:
            return Response(
                {"error": f"Deletion failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ---------------------------------------------------
    # UPLOAD IMAGE (Validated + Cached Client)
    # ---------------------------------------------------

    @action(detail=False, methods=['post'])
    def upload(self, request):

        file = request.FILES.get('file')
        name = request.data.get('name')
        category = request.data.get('category', 'general')

        if not file or not name:
            return Response(
                {"error": "Both 'file' and 'name' are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------- File Size Validation --------
        MAX_SIZE = 5 * 1024 * 1024  # 5MB
        if file.size > MAX_SIZE:
            return Response(
                {"error": "File exceeds 5MB limit."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------- MIME Type Validation --------
        ALLOWED_TYPES = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ]

        if file.content_type not in ALLOWED_TYPES:
            return Response(
                {"error": "Unsupported file type."},
                status=status.HTTP_400_BAD_REQUEST
            )

        supabase = get_supabase_client()

        file_bytes = file.read()
        file_ext = file.name.split('.')[-1]
        safe_name = name.replace(' ', '_').lower()

        file_path = (
            f"{category}/"
            f"{safe_name}_{uuid.uuid4().hex[:6]}.{file_ext}"
        )

        try:
            supabase.storage.from_('media').upload(
                file_path,
                file_bytes,
                {"content-type": file.content_type}
            )

            public_url = (
                supabase.storage
                .from_('media')
                .get_public_url(file_path)
            )

            UploadedImage.objects.create(
                name=name,
                category=category,
                supabase_path=file_path,
                public_url=public_url,
                file_size_bytes=file.size,
                uploaded_by=request.user
            )

            # Invalidate storage cache
            cache.delete("media_storage_status")

            return Response(
                {
                    "message": "Upload successful",
                    "public_url": public_url,
                    "category": category,
                    "size_kb": round(file.size / 1024, 2)
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {"error": f"Upload failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ---------------------------------------------------
    # STORAGE STATUS (Cached Analytics)
    # ---------------------------------------------------

    @action(detail=False, methods=['get'])
    def storage_status(self, request):

        cache_key = "media_storage_status"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        result = UploadedImage.objects.aggregate(
            Sum('file_size_bytes')
        )

        total_bytes = result['file_size_bytes__sum'] or 0
        max_bytes = 1073741824  # 1GB
        remaining_bytes = max_bytes - total_bytes

        data = {
            "total_used_mb": round(total_bytes / (1024 * 1024), 2),
            "remaining_mb": round(remaining_bytes / (1024 * 1024), 2),
            "percentage_used": round(
                (total_bytes / max_bytes) * 100, 2
            ),
            "total_files_uploaded":
                UploadedImage.objects.count()
        }

        cache.set(cache_key, data, timeout=60)

        return Response(data)

    # ---------------------------------------------------
    # MEDIA LIBRARY BROWSER
    # ---------------------------------------------------

    @action(detail=False, methods=['get'])
    def library(self, request):

        queryset = UploadedImage.objects.all().order_by('-uploaded_at')

        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(
                category__iexact=category
            )

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                name__icontains=search
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = UploadedImageSerializer(
                page, many=True
            )
            return self.get_paginated_response(
                serializer.data
            )

        serializer = UploadedImageSerializer(
            queryset, many=True
        )
        return Response(serializer.data)

    # ---------------------------------------------------
    # CATEGORY LIST
    # ---------------------------------------------------

    @action(detail=False, methods=['get'])
    def categories(self, request):

        categories = (
            UploadedImage.objects
            .values_list('category', flat=True)
            .distinct()
        )

        return Response(list(categories))