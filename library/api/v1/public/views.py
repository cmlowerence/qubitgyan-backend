# library\api\v1\public\views.py
from rest_framework import viewsets, permissions, mixins, exceptions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.utils import timezone
from django.db.models import Q, Exists, OuterRef, Prefetch
from datetime import timedelta
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from rest_framework.permissions import AllowAny

from library.services.email_service import queue_email

from library.models import (
    AdmissionRequest, QuizAttempt, Question,
    Option, QuestionResponse, Quiz,
    StudentProgress, Course, Enrollment,
    Notification, UserNotificationStatus,
    UserProfile, Bookmark, Resource
)

from library.api.v1.public.serializers import (
    AdmissionRequestSerializer, QuizAttemptSerializer,
    StudentQuizReadSerializer, CourseSerializer,
    NotificationSerializer, ChangePasswordSerializer,
    MyProfileSerializer, BookmarkSerializer,
    StudentProgressSerializer, QuizReviewSerializer,
    PasswordResetConfirmSerializer, PasswordResetRequestSerializer
)
User = get_user_model()

# ---------------------------------------------------
# PUBLIC ADMISSION
# ---------------------------------------------------

class PublicAdmissionViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = AdmissionRequest.objects.none()
    serializer_class = AdmissionRequestSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'admissions'
    http_method_names = ['post', 'options', 'head']

    def perform_create(self, serializer):
        admission = serializer.save()

        subject = "Application Received — QubitGyan"

        body = (
            f"Hello {admission.student_first_name} {admission.student_last_name},\n\n"
            f"We have received your application.\n"
            f"Our team will review it shortly.\n\n"
            f"You’ll receive login credentials once approved.\n\n"
            f"— QubitGyan Team"
        )

        html_body = f"""
        <h2>Application Received</h2>
        <p>Hello {admission.student_first_name} {admission.student_last_name},</p>
        <p>Your application has been successfully submitted.</p>
        <p>We’ll notify you once it’s approved.</p>
        """

        queue_email(admission.email, subject, body, html_body)


# ---------------------------------------------------
# QUIZ ATTEMPTS
# ---------------------------------------------------

class StudentQuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user) \
            .select_related('quiz__resource') \
            .prefetch_related(
                'responses__question',
                'responses__selected_option'
            ) \
            .order_by('-start_time')

    @action(detail=False, methods=['post'])
    def submit(self, request):

        quiz_id = request.data.get('quiz_id')

        try:
            quiz = Quiz.objects.get(pk=quiz_id)
        except Quiz.DoesNotExist:
            return Response({"error": "Quiz not found"}, status=404)

        # Attempt limit
        if QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz
        ).count() >= 3:
            return Response(
                {"error": "Maximum attempts reached."},
                status=status.HTTP_403_FORBIDDEN
            )

        answers_data = request.data.get('answers', [])

        answer_map = {}
        for answer in answers_data:
            q_id = answer.get('question_id')
            if q_id and q_id not in answer_map:
                answer_map[q_id] = answer.get('option_id')

        questions = Question.objects.filter(
            quiz=quiz,
            id__in=answer_map.keys()
        ).values(
            'id', 'marks_positive', 'marks_negative'
        )

        question_map = {q['id']: q for q in questions}

        selected_option_ids = [
            o_id for o_id in answer_map.values() if o_id
        ]

        valid_options = {
            (opt.id, opt.question_id): opt
            for opt in Option.objects.filter(
                id__in=selected_option_ids,
                question_id__in=question_map.keys(),
            )
        }

        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz
        )

        total_score = 0.0
        responses_to_create = []

        for q_id, o_id in answer_map.items():
            question_data = question_map.get(q_id)
            if not question_data:
                continue

            selected_option = (
                valid_options.get((o_id, q_id))
                if o_id else None
            )

            responses_to_create.append(
                QuestionResponse(
                    attempt=attempt,
                    question_id=q_id,
                    selected_option=selected_option,
                )
            )

            if selected_option:
                if selected_option.is_correct:
                    total_score += float(
                        question_data['marks_positive']
                    )
                else:
                    total_score -= float(
                        question_data['marks_negative']
                    )

        if responses_to_create:
            QuestionResponse.objects.bulk_create(
                responses_to_create
            )

        attempt.total_score = total_score
        attempt.is_completed = True
        attempt.end_time = timezone.now()
        attempt.save()

        StudentProgress.objects.update_or_create(
            user=request.user,
            resource=quiz.resource,
            defaults={'is_completed': True}
        )

        return Response(
            self.get_serializer(attempt).data
        )


# ---------------------------------------------------
# QUIZ FETCH
# ---------------------------------------------------

class StudentQuizFetchViewSet(
    mixins.RetrieveModelMixin,mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    queryset = Quiz.objects.select_related(
        'resource'
    ).prefetch_related(
        'questions__options'
    )

    serializer_class = StudentQuizReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def review(self, request, pk=None):
        quiz = self.get_object()

        has_completed = QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz,
            is_completed=True
        ).exists()

        if not has_completed:
            return Response(
                {"error" : "Nice Try! I must give you that.....But you must complete and submit the quiz befire viewing the correct answers."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = QuizReviewSerializer(quiz)
        return Response(serializer.data)


# ---------------------------------------------------
# COURSES
# ---------------------------------------------------

class PublicCourseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Course.objects.filter(
        is_published=True
    ).order_by('-created_at')

    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().select_related('root_node')

        if self.request.user.is_authenticated:
            qs = qs.annotate(
                is_enrolled_cached=Exists(
                    Enrollment.objects.filter(
                        user=self.request.user,
                        course_id=OuterRef('pk'),
                    )
                )
            )
        return qs

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        course = self.get_object()

        enrollment, created = Enrollment.objects.get_or_create(
            user=request.user,
            course=course
        )

        return Response({
            "status":
            "Enrolled successfully"
            if created else
            "Already enrolled"
        })

    @action(detail=False, methods=['get'])
    def my_courses(self, request):
        courses = self.get_queryset().filter(enrolled_students__user=request.user)
        
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)

# ---------------------------------------------------
# NOTIFICATIONS (Redis Cached)
# ---------------------------------------------------

class StudentNotificationViewSet(
    viewsets.ReadOnlyModelViewSet
):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        user_status_qs = UserNotificationStatus.objects.filter(
            user=user
        )

        return Notification.objects.filter(
            Q(target_user__isnull=True) |
            Q(target_user=user)
        ).prefetch_related(
            Prefetch(
                'usernotificationstatus_set',
                queryset=user_status_qs,
                to_attr='current_user_statuses'
            )
        ).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):

        notifications = self.get_queryset()

        objs = [
            UserNotificationStatus(
                user=request.user,
                notification=n,
                is_read=True,
                read_at=timezone.now()
            )
            for n in notifications
        ]

        UserNotificationStatus.objects.bulk_create(
            objs, ignore_conflicts=True
        )

        UserNotificationStatus.objects.filter(
            user=request.user
        ).update(is_read=True, read_at=timezone.now())

        cache.delete(f"notif_unread_{request.user.id}")

        return Response({"status": "All read"})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):

        cache_key = f"notif_unread_{request.user.id}"
        cached = cache.get(cache_key)

        if cached is not None:
            return Response({"unread_count": cached})

        total = self.get_queryset().count()

        read = UserNotificationStatus.objects.filter(
            user=request.user,
            is_read=True
        ).count()

        unread = total - read

        cache.set(cache_key, unread, timeout=120)

        return Response({"unread_count": unread})


# ---------------------------------------------------
# GAMIFICATION
# ---------------------------------------------------

class GamificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return Response({
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "total_learning_minutes": profile.total_learning_minutes,
            "last_active_date": profile.last_active_date,
        })


# ---------------------------------------------------
# CHANGE PASSWORD
# ---------------------------------------------------

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {"old_password": "Wrong password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({"status": "Password updated successfully."})


# ---------------------------------------------------
# MY PROFILE
# ---------------------------------------------------

class MyProfileView(generics.RetrieveAPIView):
    serializer_class = MyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


# ---------------------------------------------------
# BOOKMARKS
# ---------------------------------------------------

class BookmarkViewSet(viewsets.ModelViewSet):
    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Bookmark.objects.filter(
            user=self.request.user
        ).select_related('resource').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ---------------------------------------------------
# RESOURCE TRACKING
# ---------------------------------------------------

class ResourceTrackingViewSet(viewsets.ModelViewSet):
    serializer_class = StudentProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudentProgress.objects.filter(
            user=self.request.user
        ).select_related('resource').order_by('-last_accessed')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        

class PasswordResetRequestView(generics.GenericAPIView):
    """Receves email, generates secure token, and sends the recovery link."""
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(email=email).first()
        
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            token = default_token_generator.make_token(user)

            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"

            subject = "Reset Your QubitGyan Password"
            body = (
                f"Hello {user.first_name or 'Student'},\n\n"
                f"We received a request to reset your QubitGyan password.\n"
                f"Click the link below to set a new password:\n\n"
                f"{reset_link}\n\n"
                f"If you did not request this, please ignore this email. This link will expire soon."
            )
            html_body = f"""
                <h2>Password Reset Request</h2>
                <p>Hello {user.first_name or 'Student'},</p>
                <p>We received a request to reset your QubitGyan password.</p>
                <a href='{reset_link}' style='display:inline-block; padding:12px 24px; background-color:#4f46e5; color:white; text-decoration:none; border-radius:8px; font-weight:bold;'>Reset Password</a>
                <p>If you did not request this, please safely ignore this email.</p>
            """

            queue_email(user.email, subject, body, html_body)
        return Response(
            {"detail": "If an account with that email exists, a password reset link has been sent."}, 
            status=status.HTTP_200_OK
        )
    
class PasswordResetConfirmView(generics.GenericAPIView):
    """Receives the new password, verifies the token, and saves it."""
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uidb64 = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({"detail": "Your password has been reset successfully."}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "The reset link is invalid or has expired. Please request a new one."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
