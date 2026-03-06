# qubitgyan-backend\library\api\v1\manager\serializers.py
from library.serializers import (
    AdmissionRequestSerializer,
    AdminAdmissionApprovalSerializer,
    QuizSerializer,
    CourseSerializer,
    NotificationSerializer,
    UploadedImageSerializer,
    UserSerializer,
)
from library.models import Course, Notification

__all__ = [
    'AdmissionRequestSerializer',
    'AdminAdmissionApprovalSerializer',
    'QuizSerializer',
    'CourseSerializer',
    'Course',
    'NotificationSerializer',
    'Notification',
    'UploadedImageSerializer',
    'UserSerializer',
]
