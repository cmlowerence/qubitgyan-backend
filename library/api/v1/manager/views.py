from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.contrib.auth.models import User

from library.models import (
    AdmissionRequest, UserProfile, AdminAuditLog, 
    Quiz, Question, Option, Resource
)
from library.serializers import (
    AdmissionRequestSerializer, AdminAdmissionApprovalSerializer, QuizSerializer
)

class ManagerAdmissionViewSet(viewsets.ModelViewSet):
    """Admin endpoint to approve/reject students"""
    queryset = AdmissionRequest.objects.all().order_by('-created_at')
    serializer_class = AdmissionRequestSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=['patch'])
    @transaction.atomic # Ensures DB doesn't break if one step fails
    def process_application(self, request, pk=None):
        admission = self.get_object()
        serializer = AdminAdmissionApprovalSerializer(admission, data=request.data, partial=True)
        
        if serializer.is_valid():
            status_val = serializer.validated_data.get('status')
            
            # If Approved, auto-generate the User and Profile
            if status_val == 'APPROVED' and admission.status != 'APPROVED':
                # Generate a temporary password
                temp_password = f"{admission.student_name.split()[0]}@2026"
                
                user = User.objects.create_user(
                    username=admission.email.split('@')[0], 
                    email=admission.email,
                    password=temp_password,
                    first_name=admission.student_name
                )
                
                # Create the projected profile
                UserProfile.objects.create(
                    user=user,
                    created_by=request.user
                )

            # Save the admission status and log who did it
            admission.status = status_val
            admission.reviewed_by = request.user
            admission.review_remarks = serializer.validated_data.get('review_remarks', '')
            admission.save()

            # Create Security Audit Log
            AdminAuditLog.objects.create(
                admin_user=request.user,
                action=f"Changed admission {admission.email} to {status_val}"
            )

            return Response({"status": "Application Processed", "assigned_username": admission.email.split('@')[0]})
        return Response(serializer.errors, status=400)

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