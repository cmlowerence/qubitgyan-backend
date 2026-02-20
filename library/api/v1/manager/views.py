import os
import time
import uuid
from functools import lru_cache

from supabase import create_client, Client
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Sum, Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
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

from library.api.v1.manager.serializers import (
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

        try:
            supabase = get_supabase_client()
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

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

            public_url_data = (
                supabase.storage
                .from_('media')
                .get_public_url(file_path)
            )
            public_url = (
                public_url_data.get('publicURL')
                if isinstance(public_url_data, dict)
                else public_url_data
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


# ---------------------------------------------------
# MANAGER ADMISSION
# ---------------------------------------------------

# Changed from ReadOnlyModelViewSet to ModelViewSet to allow updating/editing admissions via PUT/PATCH
class ManagerAdmissionViewSet(viewsets.ModelViewSet):
    queryset = AdmissionRequest.objects.all().order_by('-created_at')
    serializer_class = AdmissionRequestSerializer
    permission_classes = [CanApproveAdmissions]

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        admission = self.get_object()

        if admission.status != 'PENDING':
            return Response(
                {"error": "This request has already been processed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        import secrets
        import string
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))

        with transaction.atomic():
            user = User.objects.create_user(
                username=admission.email,
                email=admission.email,
                password=password,
                first_name=admission.student_name,
            )
            UserProfile.objects.get_or_create(user=user)

            admission.status = 'APPROVED'
            admission.reviewed_by = request.user
            admission.review_remarks = request.data.get('remarks', '')
            admission.save()

            AdminAuditLog.objects.create(
                admin_user=request.user,
                action=f"Approved admission for {admission.email}",
                ip_address=request.META.get('REMOTE_ADDR')
            )

        subject = "Your QubitGyan Account is Ready!"
        body = (
            f"Hello {admission.student_name},\n\n"
            f"Your account has been approved.\n"
            f"Username: {admission.email}\n"
            f"Password: {password}\n\n"
            f"Please change your password after first login.\n\n"
            f"— QubitGyan Team"
        )
        html_body = f"""
        <h2>Welcome to QubitGyan!</h2>
        <p>Hello {admission.student_name},</p>
        <p>Your account has been approved.</p>
        <p><strong>Username:</strong> {admission.email}</p>
        <p><strong>Password:</strong> {password}</p>
        <p>Please change your password after logging in.</p>
        """
        queue_email(admission.email, subject, body, html_body)

        return Response({"status": "Approved", "username": admission.email})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        admission = self.get_object()

        if admission.status != 'PENDING':
            return Response(
                {"error": "This request has already been processed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        admission.status = 'REJECTED'
        admission.reviewed_by = request.user
        admission.review_remarks = request.data.get('remarks', '')
        admission.save()

        AdminAuditLog.objects.create(
            admin_user=request.user,
            action=f"Rejected admission for {admission.email}",
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({"status": "Rejected"})


# ---------------------------------------------------
# QUIZ MANAGEMENT
# ---------------------------------------------------

class QuizManagementViewSet(viewsets.ModelViewSet):
    queryset = Quiz.objects.select_related('resource').prefetch_related('questions__options').all()
    serializer_class = QuizSerializer
    permission_classes = [CanManageContent]

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Utility action to fetch all questions (and their options) for a specific quiz"""
        quiz = self.get_object()
        # Since we use QuizSerializer which includes nested questions, we can just return the quiz data, 
        # or isolate the questions list for an easier frontend map.
        serializer = self.get_serializer(quiz)
        return Response(serializer.data.get('questions', []))

    @action(detail=True, methods=['post'])
    def add_question(self, request, pk=None):
        quiz = self.get_object()
        text = request.data.get('text', '')
        image_url = request.data.get('image_url')
        marks_positive = request.data.get('marks_positive', 1)
        marks_negative = request.data.get('marks_negative', 0)
        options_data = request.data.get('options', [])

        question = Question.objects.create(
            quiz=quiz,
            text=text,
            image_url=image_url,
            marks_positive=marks_positive,
            marks_negative=marks_negative,
        )

        for opt in options_data:
            Option.objects.create(
                question=question,
                text=opt.get('text', ''),
                is_correct=opt.get('is_correct', False),
            )

        return Response({"status": "Question added", "question_id": question.id}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------
# EMAIL MANAGEMENT
# ---------------------------------------------------

class EmailManagementViewSet(viewsets.ViewSet):
    permission_classes = [IsSuperAdminOnly]

    def _serialize_emails(self, emails):
        """Helper to serialize email data consistently across actions"""
        return [
            {
                "id": e.id,
                "recipient": e.recipient_email,
                "subject": e.subject,
                "is_sent": e.is_sent,
                "created_at": e.created_at,
                "sent_at": e.sent_at,
                "error_message": e.error_message,
                "retry_count": getattr(e, 'retry_count', 0)
            }
            for e in emails
        ]

    def list(self, request):
        """Gets all emails, allows frontend to pass ?limit=100"""
        limit = int(request.query_params.get('limit', 50))
        emails = QueuedEmail.objects.all().order_by('-created_at')[:limit]
        return Response(self._serialize_emails(emails))
    

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Gets only emails waiting to be sent"""
        limit = int(request.query_params.get('limit', 50))
        emails = QueuedEmail.objects.filter(
            is_sent=False, 
            error_message__isnull=True
        ).order_by('-created_at')[:limit]
        return Response(self._serialize_emails(emails))

    @action(detail=False, methods=['get'])
    def sent(self, request):
        """Gets only successfully sent emails"""
        limit = int(request.query_params.get('limit', 50))
        emails = QueuedEmail.objects.filter(is_sent=True).order_by('-sent_at')[:limit]
        return Response(self._serialize_emails(emails))

    @action(detail=False, methods=['get'])
    def failed(self, request):
        """Gets emails that failed to send (has an error message)"""
        limit = int(request.query_params.get('limit', 50))
        emails = QueuedEmail.objects.filter(
            is_sent=False
        ).exclude(
            Q(error_message__isnull=True) | Q(error_message='')
        ).order_by('-created_at')[:limit]
        return Response(self._serialize_emails(emails))

    @action(detail=False, methods=['get'])
    def queue_status(self, request):
        """Returns counts of pending/sent/failed emails for dashboard stats"""
        pending_count = QueuedEmail.objects.filter(
            is_sent=False, error_message__isnull=True
        ).count()
        sent_count = QueuedEmail.objects.filter(is_sent=True).count()
        failed_count = QueuedEmail.objects.filter(
            is_sent=False
        ).exclude(
            Q(error_message__isnull=True) | Q(error_message='')
        ).count()
        pending = {'count': pending_count,
                   'pending_emails': self.pending(request).data}
        sent = {'count': sent_count,
                'sent_emails': self.sent(request).data}
        failed = {'count': failed_count,
                  'failed_emails': self.failed(request).data}   
        return Response({
            "pending_emails": pending,
            "sent_emails": sent,
            "failed_emails": failed
        })
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Allows an admin to manually retry a single failed email"""
        try:
            email = QueuedEmail.objects.get(pk=pk)
        except QueuedEmail.DoesNotExist:
            return Response({"error": "Email not found"}, status=status.HTTP_404_NOT_FOUND)

        if email.is_sent:
            return Response({"error": "This email has already been sent successfully."}, status=status.HTTP_400_BAD_REQUEST)

        # Assuming send_queued_email handles the try/except and sets is_sent
        success = send_queued_email(email)
        if success:
            return Response({"status": "Email retried and sent successfully!"})
        else:
            return Response({
                "error": "Retry failed", 
                "message": email.error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def flush(self, request):
        unsent = QueuedEmail.objects.filter(is_sent=False)
        count = unsent.count()
        sent_count = 0
        failed_count = 0

        for email in unsent:
            if send_queued_email(email):
                sent_count += 1
            else:
                failed_count += 1

        return Response({
            "status": f"Attempted to send {count} emails.",
            "sent": sent_count,
            "failed": failed_count,
        })


# ---------------------------------------------------
# MANAGER COURSE
# ---------------------------------------------------

class ManagerCourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all().order_by('-created_at')
    serializer_class = CourseSerializer
    permission_classes = [CanManageContent]


# ---------------------------------------------------
# MANAGER NOTIFICATION
# ---------------------------------------------------

class ManagerNotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    permission_classes = [IsSuperAdminOnly]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


# ---------------------------------------------------
# SUPER ADMIN RBAC
# ---------------------------------------------------
class SuperAdminRBACViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdminOnly]

    def get_queryset(self):
        return User.objects.filter(is_staff=True).select_related('profile').order_by('-date_joined')

    @action(detail=True, methods=['post', 'patch'])
    def update_permissions(self, request, pk=None):
        user = self.get_object()
        profile, _ = UserProfile.objects.get_or_create(user=user)

        payload = request.data.get('permissions', request.data)

        profile.can_approve_admissions = payload.get('can_approve_admissions', profile.can_approve_admissions)
        profile.can_manage_content = payload.get('can_manage_content', profile.can_manage_content)
        profile.can_manage_users = payload.get('can_manage_users', profile.can_manage_users)
        profile.save()
        user.refresh_from_db()

        return Response({
            "status": "Permissions updated",
            "user": UserSerializer(user, context={"request": request}).data
        })
    
