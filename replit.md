# QubitGyan API

## Overview
QubitGyan is a Django REST Framework backend API for an educational platform. It provides APIs for course management, quizzes, student admissions, gamification, notifications, and more.

## Recent Changes
- Configured for Replit environment (Feb 2026)
- Fixed missing serializer (StudentQuestionSerializer)
- Added missing view classes (GamificationViewSet, ChangePasswordView, MyProfileView, BookmarkViewSet, ResourceTrackingViewSet, ManagerAdmissionViewSet, QuizManagementViewSet, EmailManagementViewSet, ManagerCourseViewSet, ManagerNotificationViewSet, SuperAdminRBACViewSet)
- Configured local memory cache fallback when Redis is unavailable
- Removed file-based logging (console only)

## Project Architecture
- **Framework**: Django 5.0.1 + Django REST Framework 3.14.0
- **Database**: PostgreSQL (via DATABASE_URL environment variable)
- **Authentication**: JWT via djangorestframework-simplejwt
- **Cache**: Redis (django-redis) with local memory fallback
- **Static Files**: WhiteNoise
- **External Services**: Supabase (image storage), Gmail SMTP (email)

## Directory Structure
- `qubitgyan/` - Django project settings and configuration
- `library/` - Main Django app
  - `models.py` - Database models
  - `serializers.py` - DRF serializers
  - `views.py` - Core viewsets
  - `urls.py` - URL routing
  - `permissions.py` - Custom permission classes
  - `api/v1/public/views.py` - Student-facing API endpoints
  - `api/v1/manager/views.py` - Admin/manager API endpoints
  - `api/v1/system/views.py` - Health check endpoint
  - `services/email_service.py` - Email queue service
  - `middleware/` - Request/error logging middleware

## Key API Endpoints
- `GET /api/v1/health/` - Health check
- `POST /api/token/` - JWT token obtain
- `POST /api/token/refresh/` - JWT token refresh
- `GET /api/v1/nodes/` - Knowledge tree
- `GET /api/v1/resources/` - Learning resources
- `POST /api/v1/public/admissions/` - Student admission requests
- `GET /api/v1/public/courses/` - Available courses

## Running
- Development: `gunicorn --bind 0.0.0.0:5000 --workers 2 qubitgyan.wsgi:application`
- The server runs on port 5000

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection string (auto-configured)
- `SECRET_KEY` - Django secret key (optional, has fallback)
- `REDIS_URL` - Redis connection URL (optional)
- `SUPABASE_URL` - Supabase project URL (for image uploads)
- `SUPABASE_SR_KEY` - Supabase service role key
- `SMTP_USER` - Gmail SMTP username
- `SMTP_PASSWORD` - Gmail SMTP password
