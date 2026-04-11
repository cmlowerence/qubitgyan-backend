from django.urls import path
from .views.public import (
    QuizGenerateView, 
    QuizAnswerSubmitView, 
    QuizCompleteView, 
    QuizReviewView
)
from .views.manager import BulkCSVUploadView, AdminQuestionBankView

urlpatterns = [
    # POST: Generate a new mock test or pop quiz
    path('public/generate/', QuizGenerateView.as_view(), name='assessment-public-generate'),
    
    # PATCH: Auto-save a student's answer as they click through the test
    path('public/attempts/<uuid:attempt_id>/submit/', QuizAnswerSubmitView.as_view(), name='assessment-public-submit-answer'),
    
    # POST: Finalize the test, calculate the score, and award XP
    path('public/attempts/<uuid:attempt_id>/complete/', QuizCompleteView.as_view(), name='assessment-public-complete'),
    
    # GET: Fetch the detailed response sheet with explanations and correct answers
    path('public/attempts/<uuid:attempt_id>/review/', QuizReviewView.as_view(), name='assessment-public-review'),
    
    # GET: View the master Question Bank
    path('manager/questions/', AdminQuestionBankView.as_view(), name='assessment-manager-questions'),
    
    # POST: Upload the master CSV file to populate the database
    path('manager/questions/bulk-upload/', BulkCSVUploadView.as_view(), name='assessment-manager-bulk-upload'),
]