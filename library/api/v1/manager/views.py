import os
import time
from supabase import create_client, Client
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Sum
import uuid
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from library.permissions import IsSuperAdminOnly
from library.services.email_service import queue_email
from library.models import QueuedEmail
from library.services.email_service import send_queued_email

from library.models import (
    AdmissionRequest, UserProfile, AdminAuditLog, 
    Quiz, Question, Option, Resource, QueuedEmail,
    UploadedImage
)
from library.serializers import (
    AdmissionRequestSerializer, AdminAdmissionApprovalSerializer,
    QuizSerializer, CourseSerializer, Course, NotificationSerializer, 
    Notification, UploadedImageSerializer, UserSerializer
)

class ManagerAdmissionViewSet(viewsets.ModelViewSet):
    """Admin endpoint to approve/reject students"""
    queryset = AdmissionRequest.objects.all().order_by('-created_at')
    serializer_class = AdmissionRequestSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=['patch'])
    @transaction.atomic 
    def process_application(self, request, pk=None):
        admission = self.get_object()
        serializer = AdminAdmissionApprovalSerializer(admission, data=request.data, partial=True)
        
        if serializer.is_valid():
            status_val = serializer.validated_data.get('status')
            
            if status_val == 'APPROVED' and admission.status != 'APPROVED':
                # Generate a temporary password (e.g., john@2026!Qubit)
                base_username = admission.email.split('@')[0]
                temp_password = f"{base_username}@2026!Qubit"
                
                # UPDATE: Use the email address directly as the username
                user = User.objects.create_user(
                    username=admission.email, 
                    email=admission.email, 
                    password=temp_password, 
                    first_name=admission.student_name
                )
                UserProfile.objects.create(user=user, created_by=request.user)

                # 1. Plain Text Fallback
                plain_text_body = (
                    f"Hello {admission.student_name},\n\n"
                    f"Your application is approved! Here are your secure login details:\n"
                    f"Username (Your Email): {admission.email}\n"
                    f"Password: {temp_password}\n\n"
                    f"Please log in and change your password immediately."
                )

                # 2. Professional HTML Template
                html_body = f"""
                <!DOCTYPE html>
                <html>
                <head>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f5; margin: 0; padding: 0; }}
                    .container {{ max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                    .header {{ background-color: #0F172A; padding: 30px; text-align: center; }}
                    .logo-text {{ color: #ffffff; font-size: 28px; font-weight: 900; letter-spacing: 2px; margin: 0; }}
                    .logo-accent {{ color: #F59E0B; }}
                    .content {{ padding: 40px 30px; color: #334155; line-height: 1.6; }}
                    .credentials {{ background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 25px; margin: 25px 0; text-align: center; }}
                    .cred-item {{ margin: 12px 0; font-size: 16px; }}
                    .cred-value {{ font-weight: bold; color: #0F172A; font-family: monospace; font-size: 16px; padding: 6px 12px; background: #e2e8f0; border-radius: 4px; display: inline-block; margin-left: 10px; }}
                    .button-container {{ text-align: center; margin-top: 35px; }}
                    .button {{ background-color: #F59E0B; color: #ffffff !important; text-decoration: none; padding: 14px 28px; border-radius: 6px; font-weight: bold; display: inline-block; font-size: 16px; }}
                    .footer {{ text-align: center; padding: 20px; color: #94a3b8; font-size: 12px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; }}
                </style>
                </head>
                <body>
                <div class="container">
                    <div class="header">
                        <h1 class="logo-text">QUBIT<span class="logo-accent">GYAN</span></h1>
                    </div>
                    <div class="content">
                        <h2 style="color: #0F172A; margin-top: 0;">Welcome aboard, {admission.student_name}!</h2>
                        <p>We are thrilled to let you know that your application has been successfully approved. Your learning environment is now ready.</p>
                        
                        <div class="credentials">
                            <p style="margin-top: 0; color: #64748b; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Your Secure Credentials</p>
                            <div class="cred-item">Username: <span class="cred-value">{admission.email}</span></div>
                            <div class="cred-item">Password: <span class="cred-value">{temp_password}</span></div>
                        </div>

                        <p>For your security, we highly recommend navigating to your profile settings and changing your password immediately after your first login.</p>
                        
                        <div class="button-container">
                            <a href="https://qubitgyan.vercel.app/login" class="button">Log In to Your Dashboard</a>
                        </div>
                    </div>
                    <div class="footer">
                        &copy; 2026 QubitGyan Learning. All rights reserved.<br>
                        This is an automated message, please do not reply.
                    </div>
                </div>
                </body>
                </html>
                """
                
                # 3. Save to Queue
                queue_email(
                    recipient=admission.email,
                    subject="Welcome to QubitGyan - Application Approved!",
                    body=plain_text_body,
                    html_body=html_body
                )
            admission.status = status_val
            admission.reviewed_by = request.user
            admission.review_remarks = serializer.validated_data.get('review_remarks', '')
            admission.save()

            AdminAuditLog.objects.create(
                admin_user=request.user, action=f"Changed admission {admission.email} to {status_val}"
            )

            # Note: We return admission.email here so your frontend knows exactly what was assigned
            return Response({
                "status": "Application Processed, Email Queued", 
                "assigned_username": admission.email
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EmailManagementViewSet(viewsets.ViewSet):
    """Allows Superadmins to control the flow of outgoing emails"""
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def queue_status(self, request):
        pending = QueuedEmail.objects.filter(is_sent=False).count()
        sent = QueuedEmail.objects.filter(is_sent=True).count()
        return Response({"pending_emails": pending, "total_sent": sent})

    @action(detail=False, methods=['post'])
    def dispatch_batch(self, request):
        # Keep request time bounded to avoid platform worker timeouts.
        limit = min(int(request.data.get('limit', 10)), 25)
        max_seconds = min(int(request.data.get('max_seconds', 20)), 25)
        started_at = time.monotonic()
        pending_emails = QueuedEmail.objects.filter(is_sent=False)[:limit]
        
        sent_count = 0
        failed_count = 0

        for queued_email in pending_emails:
            if time.monotonic() - started_at >= max_seconds:
                break
            try:
                send_mail(
                    subject=queued_email.subject,
                    message=queued_email.body,
                    html_message=queued_email.html_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[queued_email.recipient_email],
                    fail_silently=False,
                )
                queued_email.is_sent = True
                queued_email.sent_at = timezone.now()
                queued_email.save()
                sent_count += 1
            except Exception as e:
                queued_email.error_message = str(e)
                queued_email.save()
                failed_count += 1

        return Response({"message": "Batch dispatch completed.", "emails_sent": sent_count, "emails_failed": failed_count})
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        emails = QueuedEmail.objects.filter(is_sent=False)
        data = [
            {
                "id": e.id,
                "recipient": e.recipient_email,
                "subject": e.subject,
                "created_at": e.created_at,
                "error": e.error_message,
            }
            for e in emails
        ]
        return Response(data)


    @action(detail=False, methods=['get'])
    def sent(self, request):
        emails = QueuedEmail.objects.filter(is_sent=True)
        data = [
            {
                "id": e.id,
                "recipient": e.recipient_email,
                "subject": e.subject,
                "sent_at": e.sent_at,
            }
            for e in emails
        ]
        return Response(data)


    @action(detail=False, methods=['get'])
    def failed(self, request):
        emails = QueuedEmail.objects.filter(is_sent=False).exclude(error_message="")
        data = [
            {
                "id": e.id,
                "recipient": e.recipient_email,
                "subject": e.subject,
                "error": e.error_message,
            }
            for e in emails
        ]
        return Response(data)


    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        email = QueuedEmail.objects.get(pk=pk)
        success = send_queued_email(email)

        if success:
            return Response({"status": "Email sent successfully"})
        return Response({"status": "Retry failed", "error": email.error_message})

class QuizManagementViewSet(viewsets.ModelViewSet):
    """
    Admin endpoint to completely build a Quiz. 
    Accepts deeply nested JSON for Questions and Options.
    """
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAdminUser]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Custom creation to handle deeply nested Questions and Options"""
        data = request.data
        
        # 1. Ensure the underlying Resource exists and is a QUIZ
        resource_id = data.get('resource')
        try:
            resource = Resource.objects.get(id=resource_id, resource_type='QUIZ')
        except Resource.DoesNotExist:
            return Response({"error": "Valid QUIZ Resource ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Create the Quiz details
        quiz = Quiz.objects.create(
            resource=resource,
            passing_score_percentage=data.get('passing_score_percentage', 50),
            time_limit_minutes=data.get('time_limit_minutes', 30)
        )

        # 3. Process Nested Questions and Options
        questions_data = data.get('questions', [])
        for q_data in questions_data:
            question = Question.objects.create(
                quiz=quiz,
                text=q_data.get('text'),
                image_url=q_data.get('image_url', ''),
                marks_positive=q_data.get('marks_positive', 1.00),
                marks_negative=q_data.get('marks_negative', 0.00),
                order=q_data.get('order', 0)
            )
            
            # Process Nested Options for this Question
            options_data = q_data.get('options', [])
            for o_data in options_data:
                Option.objects.create(
                    question=question,
                    text=o_data.get('text'),
                    is_correct=o_data.get('is_correct', False)
                )

        # Return the freshly created quiz fully serialized
        serializer = self.get_serializer(quiz)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class ManagerCourseViewSet(viewsets.ModelViewSet):
    """Allows Admins to create, edit, and publish Course wrappers"""
    queryset = Course.objects.all().order_by('-created_at')
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAdminUser]

    def check_permissions(self, request):
        super().check_permissions(request)
        # Extra security: Enforce RBAC flag
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if not request.user.is_superuser and not profile.can_manage_content:
            self.permission_denied(request, message="You do not have permission to manage courses.")

class ManagerNotificationViewSet(viewsets.ModelViewSet):
    """Allows Admins to send global or targeted messages"""
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        # Automatically set the sender to the Admin making the request
        serializer.save(sender=self.request.user)

class SuperAdminRBACViewSet(viewsets.ViewSet):
    """STRICTLY FOR SUPERUSERS: Manage permissions of other admins"""
    permission_classes = [IsSuperAdminOnly]

    @action(detail=False, methods=['get'])
    def list_admins(self, request):
        """Returns all staff users and their current permission flags"""
        admins = User.objects.filter(is_staff=True, is_superuser=False).select_related('profile')
        data = []
        for admin in admins:
            profile = getattr(admin, 'profile', None)
            if profile is None:
                profile, _ = UserProfile.objects.get_or_create(user=admin)
            data.append({
                "id": admin.id,
                "username": admin.username,
                "email": admin.email,
                "avatar": profile.avatar_url if profile.avatar_url else None,
                "permissions": {
                    "can_approve_admissions": profile.can_approve_admissions,
                    "can_manage_content": profile.can_manage_content,
                    "can_manage_users": profile.can_manage_users
                }
            })
        return Response(data)

    @action(detail=True, methods=['patch'])
    def update_permissions(self, request, pk=None):
        """Toggle specific permissions for an admin"""
        try:
            admin_user = User.objects.get(pk=pk, is_staff=True, is_superuser=False)
            profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        except User.DoesNotExist:
            return Response({"error": "Admin not found"}, status=status.HTTP_404_NOT_FOUND)

        perms = request.data.get('permissions', {})
        if 'can_approve_admissions' in perms:
            profile.can_approve_admissions = perms['can_approve_admissions']
        if 'can_manage_content' in perms:
            profile.can_manage_content = perms['can_manage_content']
        if 'can_manage_users' in perms:
            profile.can_manage_users = perms['can_manage_users']
        
        profile.save()
        
        # Log this highly sensitive action
        AdminAuditLog.objects.create(
            admin_user=request.user,
            action=f"Updated permissions for admin: {admin_user.username}"
        )

        # Return the updated user payload so clients can refresh caches immediately
        user_data = UserSerializer(admin_user).data
        return Response({"status": "Permissions updated successfully!", "user": user_data})
    
class ImageManagementViewSet(viewsets.ModelViewSet):
    """Superadmin endpoint for uploading, listing, and deleting images"""
    queryset = UploadedImage.objects.all().order_by('-uploaded_at')
    serializer_class = UploadedImageSerializer
    permission_classes = [IsSuperAdminOnly] 
    parser_classes = [MultiPartParser, FormParser]

    def destroy(self, request, *args, **kwargs):
        """Deletes the image from Django AND frees up space in Supabase"""
        image_record = self.get_object()
        
        try:
            # 1. Connect to Supabase
            # Use the service-role key for server-side operations; fall back to legacy key if present
            supabase_key = getattr(settings, 'SUPABASE_SR_KEY', None) or getattr(settings, 'SUPABASE_KEY', None)
            supabase: Client = create_client(settings.SUPABASE_URL, supabase_key)
            
            # 2. Delete the actual file from the 'media' bucket
            supabase.storage.from_('media').remove([image_record.supabase_path])
            
            # 3. Delete the tracking record from Django DB
            image_record.delete()
            
            return Response({"message": "Image deleted and storage freed!"}, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            return Response({"error": f"Failed to delete from Supabase: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def upload(self, request):
        """Uploads a file to Supabase and returns the public URL"""
        file = request.FILES.get('file')
        name = request.data.get('name')
        category = request.data.get('category', 'general')

        if not file or not name:
            return Response({"error": "Both 'file' and 'name' are required."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Connect to Supabase
        url: str = settings.SUPABASE_URL
        # prefer SR (service role) key for server-side uploads; allow legacy SUPABASE_KEY for existing deployments
        key: str = getattr(settings, 'SUPABASE_SR_KEY', None) or getattr(settings, 'SUPABASE_KEY', None)
        if not url or not key:
            return Response({"error": "Supabase keys missing from server config."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        supabase: Client = create_client(url, key)
        file_bytes = file.read()
        file_ext = file.name.split('.')[-1]
        safe_name = name.replace(' ', '_').lower()
        file_path = f"{category}/{safe_name}_{uuid.uuid4().hex[:6]}.{file_ext}"

        try:
            supabase.storage.from_('media').upload(
                file_path, 
                file_bytes, 
                {"content-type": file.content_type}
            )
            public_url = supabase.storage.from_('media').get_public_url(file_path)
            image_record = UploadedImage.objects.create(
                name=name,
                category=category,
                supabase_path=file_path,
                public_url=public_url,
                file_size_bytes=file.size,
                uploaded_by=request.user
            )

            return Response({
                "message": "Upload successful",
                "public_url": public_url,
                "category": category,
                "size_kb": round(file.size / 1024, 2)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"Supabase Upload Failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def storage_status(self, request):
        """Calculates how much of the 1GB free tier is used"""
        # Sum all file sizes in the database
        result = UploadedImage.objects.aggregate(Sum('file_size_bytes'))
        total_bytes = result['file_size_bytes__sum'] or 0
        
        max_bytes = 1073741824 # Exactly 1 GB
        remaining_bytes = max_bytes - total_bytes

        return Response({
            "total_used_mb": round(total_bytes / (1024 * 1024), 2),
            "remaining_mb": round(remaining_bytes / (1024 * 1024), 2),
            "percentage_used": round((total_bytes / max_bytes) * 100, 2),
            "total_files_uploaded": UploadedImage.objects.count()
        })
    
