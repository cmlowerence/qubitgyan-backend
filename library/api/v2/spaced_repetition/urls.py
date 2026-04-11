from django.urls import path
from .views.public import DueFlashcardsView, SubmitReviewView, WordInteractionView
from .views.manager import StudentMasteryListView, StudentReviewLogAuditView, ResetStudentMasteryView

urlpatterns = [
    #! ------------------------------------------------------------------
    #! PUBLIC ENDPOINTS (For authenticated students learning on the app)
    #! ------------------------------------------------------------------
    
    #! GET: Fetches the 50 cards due for review today
    path('public/due/', DueFlashcardsView.as_view(), name='sr-public-due-flashcards'),
    
    #! POST: Submits the SM-2 grade (0-5) and calculates the next review date
    path('public/review/', SubmitReviewView.as_view(), name='sr-public-submit-review'),
    
    #! PATCH: Mutes a word or adds a custom mnemonic note
    path('public/words/<uuid:word_id>/interact/', WordInteractionView.as_view(), name='sr-public-word-interact'),


    #! ------------------------------------------------------------------
    #! MANAGER ENDPOINTS (For Admins auditing or fixing student decks)
    #! ------------------------------------------------------------------
    
    #! GET: View a specific student's entire flashcard deck and mastery levels
    path('manager/students/<int:user_id>/mastery/', StudentMasteryListView.as_view(), name='sr-manager-student-mastery'),
    
    #! GET: View the raw log of every card flip a student did (to catch spam clicking)
    path('manager/students/<int:user_id>/logs/', StudentReviewLogAuditView.as_view(), name='sr-manager-student-logs'),
    
    #! POST: Emergency reset for a specific word in a student's deck
    path('manager/students/<int:user_id>/words/<uuid:word_id>/reset/', ResetStudentMasteryView.as_view(), name='sr-manager-reset-mastery'),
]