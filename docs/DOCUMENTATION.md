# 1. Project Overview

*QubitGyan* is a production-ready Learning Management System (LMS) backend built using:

- Django 5
- Django REST Framework
- PostgreSQL
- Redis (Caching Layer)
- Supabase (Media Storage)
- JWT Authentication (SimpleJWT)

---

Core Capabilities

- Student onboarding & admissions
- Hierarchical knowledge delivery
- Course enrollment
- Quiz & assessment engine
- Notifications system
- Gamification tracking
- Media storage & delivery
- Admin RBAC control panel

---

# 2. Project Structure

```
qubitgyan/
│
├── qubitgyan/                # Project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── library/                 # Core LMS application
│   │
│   ├── models.py
│   ├── serializers.py
│   ├── permissions.py
│   ├── middleware/
│   ├── services/
│   ├── management/
│   │
│   ├── api/v1/
│   │   ├── public/          # Student endpoints
│   │   ├── manager/         # Admin endpoints
│   │   └── system/          # Health & monitoring
│   │
│   └── views.py             # Knowledge tree + admin core
│
└── docs/
```
---

# 3. Authentication

## Token Obtain

```
POST /api/token/
```

### Request
```

{
  "username": "student@email.com",
  "password": "password"
}
```
### Response
```
{
  "access": "JWT_ACCESS_TOKEN",
  "refresh": "JWT_REFRESH_TOKEN"
}
```
JWT is required in headers:
```
Authorization: Bearer <token>
```
---

# 4. Role-Based Access Control (RBAC)

*Role| Permissions*
Student| Learning access only
Admin| Content + operations
Superadmin| Full system control

### Permission Flags

- "can\_manage\_content"
- "can\_approve\_admissions"
- "can\_manage\_users"

---

# 5. Student Endpoints

---

## 5.1 Admission Request
```
POST /api/v1/public/admissions/
```
### Request
```
{
  "student_name": "John Doe",
  "email": "john@email.com"
}
```
### Response
```
{
  "id": 12,
  "status": "PENDING"
}
```
Spam protected via throttling.

---

## 5.2 Fetch Courses
```
GET /api/v1/public/courses/
```
### Response
```
[
  {
    "id": 1,
    "title": "Physics",
    "is_enrolled_cached": true
  }
]
```
---

## 5.3 Enroll Course
```
POST /api/v1/public/courses/{id}/enroll/
```
### Response
```
{ "status": "Enrolled successfully" }
```
---

## 5.4 My Courses
```
GET /api/v1/public/courses/my_courses/
```
---

# 6. Knowledge Tree System

The Knowledge Tree represents the hierarchical structure:

### Domain → Subject → Topic → Subtopic

Each node contains:

- Child nodes
- Attached resources
- Resource count
- Child count

---

## Endpoint
```
GET /api/v1/tree/
```
---

## Depth-Based Fetching

Tree payload can be controlled using depth.

### Query Parameter
```
?depth=<value>
```
### Supported Values

*Depth| Result*
depth=1| Root nodes only
depth=2| Root + children
depth=3| Root + grandchildren
depth=full| Complete tree
(none)| Complete tree

---

## Examples
```
GET /api/v1/tree/?depth=1
GET /api/v1/tree/?depth=2
GET /api/v1/tree/?depth=full
```
---

## Sample Response
```
[
  {
    "id": 1,
    "name": "Physics",
    "resource_count": 12,
    "items_count": 3,
    "children": [
      {
        "id": 5,
        "name": "Mechanics",
        "resource_count": 6,
        "items_count": 2,
        "children": []
      }
    ]
  }
]
```
---

## Redis Caching Strategy

Each depth level is cached separately.

### *Depth| Cache Key
1| knowledge\_tree\_depth_1
2| knowledge\_tree\_depth_2
full| knowledge\_tree\_depth_full

Cache TTL: *300 seconds*

---

### Cache Invalidation

Cache clears automatically when:

- Node created
- Node updated
- Node deleted

---

### Performance Benefits

Before:

- Full recursive serialization
- Large payloads
- Slower rendering

After:

- Controlled payload size
- Redis caching
- Reduced DB load

---

# 7. Quiz System

---

## 7.1 Fetch Quiz
```
GET /api/v1/public/quiz/{id}/
```
### Response
```
{
  "id": 5,
  "questions": [
    {
      "id": 10,
      "text": "Speed of light?",
      "options": [
        { "id": 1, "text": "3x10^8" }
      ]
    }
  ]
}
```
---

## 7.2 Submit Quiz
```
POST /api/v1/public/quiz-attempts/submit/
```
### Request
```
{
  "quiz_id": 5,
  "answers": [
    { "question_id": 10, "option_id": 1 }
  ]
}
```
### Response
```
{
  "total_score": 8,
  "is_completed": true
}
```
Attempt limit: *3*

---

# 8. Notifications

---

## Fetch
```
GET /api/v1/public/notifications/
```
## Mark All Read
```
POST /api/v1/public/notifications/mark_all_read/
```
## Unread Count
```
GET /api/v1/public/notifications/unread_count/
```
```
{ "unread_count": 4 }
```
Redis cached.

---

# 9. Gamification
```
POST /api/v1/public/gamification/ping/
```
Tracks:

- Learning minutes
- Current streak
- Longest streak

---

# 10. Bookmarks
```
GET    /api/v1/public/bookmarks/
POST   /api/v1/public/bookmarks/
DELETE /api/v1/public/bookmarks/{id}/
```
---

# 11. Resource Progress Tracking
```
POST /api/v1/public/resource-tracking/save_timestamp/
```
---

# 12. Admin Endpoints

---

## 12.1 Admissions Processing
```
PATCH /api/v1/manager/admissions/{id}/process_application/
```
---

## 12.2 Quiz Builder
```
POST /api/v1/manager/quizzes/
```
Supports nested payloads.

---

## 12.3 Course Management
```
/api/v1/manager/courses/
```
CRUD enabled.

---

## 12.4 Notifications
```
/api/v1/manager/notifications/
```
---

## 12.5 Email Queue
```
GET  /queue_status/
POST /dispatch_batch/
GET  /pending/
GET  /sent/
GET  /failed/
POST /{id}/retry/
```
---

# 13. Media Management

---

## Upload
```
POST /api/v1/manager/media/upload/
```

## Validation:

- Max 5MB
- JPEG / PNG / WebP

---

## Media Library
```
GET /media/library/
```
Filters:
```
?category=
?search=
```
---

## Storage Status
```
GET /media/storage_status/
```
---

# 14. Observability

---

## Health Check
```
GET /api/v1/system/health/
```
```
{
  "status": "healthy",
  "database": "ok",
  "cache": "ok"
}
```
---

# 15. Caching Layer

Redis caches:

- Knowledge tree
- Notifications
- Media storage stats
- Email dispatch locks

---

# 16. Database Indexing

Indexes applied on:

- QuizAttempt
- Enrollment
- StudentProgress
- Notification
- KnowledgeNode
- Resource
- Bookmark

---

# 17. Email Infrastructure

Queue → Retry → Batch dispatch

Non-blocking SMTP delivery.

---

# 18. Deployment Stack

Recommended production stack:

- Gunicorn
- Nginx
- Redis
- PostgreSQL
- Supabase
- Whitenoise

---

# END OF DOCUMENTATION