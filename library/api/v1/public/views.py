# library\api\v1\public\views.py
from rest_framework import viewsets, permissions, mixins, exceptions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.utils import timezone
from django.db.models import Q, Exists, OuterRef, Prefetch
from datetime import timedelta
from library.models import (
    AdmissionRequest, QuizAttempt, Question, 
    Option, QuestionResponse, Quiz, StudentProgress, Course, Enrollment, Notification,UserNotificationStatus, UserProfile, Bookmark, Resource
)
from library.serializers import AdmissionRequestSerializer, QuizAttemptSerializer, StudentQuizReadSerializer, CourseSerializer, NotificationSerializer, ChangePasswordSerializer, MyProfileSerializer, BookmarkSerializer

class PublicAdmissionViewSet(viewsets.ModelViewSet):
    """Spam-protected public endpoint for students to request an account"""
    queryset = AdmissionRequest.objects.all()
    serializer_class = AdmissionRequestSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'admissions' # Limits to 5/day per IP (set in settings.py)

    def get_queryset(self):
        # Public users cannot GET the list of applications
        if self.request.method == 'GET':
            raise exceptions.MethodNotAllowed("GET")
        return super().get_queryset()
    
class StudentQuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # PATCH 4: Performance Optimization
        # select_related and prefetch_related fetch all nested data in exactly 3 efficient queries, 
        # preventing the database from choking when a student checks their history.
        return QuizAttempt.objects.filter(user=self.request.user) \
            .select_related('quiz__resource') \
            .prefetch_related('responses__question', 'responses__selected_option') \
            .order_by('-start_time')

    @action(detail=False, methods=['post'])
    def submit(self, request):
        quiz_id = request.data.get('quiz_id')
        try:
            quiz = Quiz.objects.get(pk=quiz_id)
        except Quiz.DoesNotExist:
            return Response({"error": "Quiz not found"}, status=404)

        answers_data = request.data.get('answers', [])

        # Keep only the first answer per question to prevent duplicate grading.
        answer_map = {}
        for answer in answers_data:
            q_id = answer.get('question_id')
            if q_id and q_id not in answer_map:
                answer_map[q_id] = answer.get('option_id')

        # Fetch all valid questions for this quiz in one query.
        valid_questions = {
            q.id: q
            for q in Question.objects.filter(id__in=answer_map.keys(), quiz=quiz)
        }

        # Fetch only the selected options that belong to those valid questions.
        selected_option_ids = [o_id for o_id in answer_map.values() if o_id]
        valid_options = {
            (opt.id, opt.question_id): opt
            for opt in Option.objects.filter(
                id__in=selected_option_ids,
                question_id__in=valid_questions.keys(),
            )
        }

        attempt = QuizAttempt.objects.create(user=request.user, quiz=quiz)
        total_score = 0.0
        responses_to_create = []

        for q_id, o_id in answer_map.items():
            question = valid_questions.get(q_id)
            if not question:
                # Ignore injected foreign question IDs.
                continue

            selected_option = valid_options.get((o_id, q_id)) if o_id else None
            responses_to_create.append(
                QuestionResponse(
                    attempt=attempt,
                    question=question,
                    selected_option=selected_option,
                )
            )

            if selected_option:
                if selected_option.is_correct:
                    total_score += float(question.marks_positive)
                else:
                    total_score -= float(question.marks_negative)

        if responses_to_create:
            QuestionResponse.objects.bulk_create(responses_to_create)

        # Finalize Attempt
        attempt.total_score = total_score
        attempt.is_completed = True
        attempt.end_time = timezone.now()
        attempt.save()

        # Update standard LMS StudentProgress
        StudentProgress.objects.update_or_create(
            user=request.user,
            resource=quiz.resource,
            defaults={'is_completed': True}
        )

        serializer = self.get_serializer(attempt)
        return Response(serializer.data)

class StudentQuizFetchViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Allows students to fetch a specific quiz payload safely"""
    queryset = Quiz.objects.all()
    serializer_class = StudentQuizReadSerializer
    permission_classes = [permissions.IsAuthenticated]

class PublicCourseViewSet(viewsets.ReadOnlyModelViewSet):
    """Students can browse all published courses and enroll"""
    queryset = Course.objects.filter(is_published=True).order_by('-created_at')
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('root_node')
        if self.request.user.is_authenticated:
            return queryset.annotate(
                is_enrolled_cached=Exists(
                    Enrollment.objects.filter(
                        user=self.request.user,
                        course_id=OuterRef('pk'),
                    )
                )
            )
        return queryset

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """Action for a student to enroll in a course"""
        course = self.get_object()
        enrollment, created = Enrollment.objects.get_or_create(user=request.user, course=course)
        
        if created:
            return Response({"status": "Enrolled successfully"}, status=status.HTTP_201_CREATED)
        return Response({"status": "Already enrolled"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def my_courses(self, request):
        """Returns ONLY the courses the student is enrolled in"""
        enrollments = Enrollment.objects.filter(user=request.user).select_related('course')
        courses = [e.course for e in enrollments]
        
        # We pass the request context so the Serializer knows who is asking (for the is_enrolled field)
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)

class GamificationViewSet(viewsets.ViewSet):
    """Handles streaks and learning time tracking"""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def ping(self, request):
        """
        Frontend should call this every 5 minutes while the student is active.
        Calculates streaks and total time spent.
        """
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        today = timezone.now().date()

        # Add learning time (default 5 minutes per ping)
        minutes_to_add = int(request.data.get('minutes', 5))
        profile.total_learning_minutes += minutes_to_add

        # Calculate Daily Streak
        if profile.last_active_date == today:
            pass # Already active today, streak is maintained
        elif profile.last_active_date == today - timedelta(days=1):
            profile.current_streak += 1 # Active yesterday, increment streak!
        else:
            profile.current_streak = 1 # Missed a day, reset streak to 1

        # Check for Longest Streak Record
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak

        profile.last_active_date = today
        profile.save()

        return Response({
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "total_learning_minutes": profile.total_learning_minutes
        })

class StudentNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Students can fetch their notifications and mark them as read"""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Fetch GLOBAL notifications (target_user is null) OR targeted specifically to this user
        user_status_qs = UserNotificationStatus.objects.filter(user=self.request.user)
        return Notification.objects.filter(
            Q(target_user__isnull=True) | Q(target_user=self.request.user)
        ).prefetch_related(
            Prefetch('usernotificationstatus_set', queryset=user_status_qs, to_attr='current_user_statuses')
        ).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Creates a record saying this specific student read this message"""
        notification = self.get_object()
        
        status_record, _ = UserNotificationStatus.objects.get_or_create(
            user=request.user, 
            notification=notification
        )
        
        status_record.is_read = True
        status_record.read_at = timezone.now()
        status_record.save()
        
        return Response({"status": "Marked as read"}, status=status.HTTP_200_OK)
    
class ChangePasswordView(generics.UpdateAPIView):
    """
    Endpoint for students (or admins) to change their password.
    Requires a valid JWT token.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Securely grab the user from the JWT token, not the URL
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # 1. Verify the old password is correct
            if not user.check_password(serializer.data.get("old_password")):
                return Response(
                    {"old_password": ["Incorrect current password."]}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 2. Hash and save the new password
            user.set_password(serializer.data.get("new_password"))
            user.save()
            
            return Response(
                {"status": "Password updated successfully."}, 
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class MyProfileView(generics.RetrieveAPIView):
    """Allows a student to fetch their own gamification stats and details"""
    serializer_class = MyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Securely fetch profile using the JWT token identity
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

class BookmarkViewSet(viewsets.ModelViewSet):
    """Students can list, create, and delete their saved resources"""
    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # ONLY return the logged-in student's bookmarks
        return Bookmark.objects.filter(user=self.request.user).select_related('resource')

    def perform_create(self, serializer):
        # Automatically attach the logged-in user to the bookmark
        serializer.save(user=self.request.user)
    
class ResourceTrackingViewSet(viewsets.ViewSet):
    """Dedicated endpoints for tracking exact media progress"""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def save_timestamp(self, request):
        """Frontend calls this when a video pauses to save the exact second"""
        resource_id = request.data.get('resource_id')
        timestamp = request.data.get('resume_timestamp', 0)
        
        try:
            resource = Resource.objects.get(pk=resource_id)
            progress, _ = StudentProgress.objects.get_or_create(
                user=request.user, 
                resource=resource
            )
            
            progress.resume_timestamp = int(timestamp)
            progress.save()
            
            return Response({"status": "Progress saved", "timestamp": progress.resume_timestamp})
        except Resource.DoesNotExist:
            return Response({"error": "Resource not found"}, status=status.HTTP_404_NOT_FOUND)
