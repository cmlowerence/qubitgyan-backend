# 🚀 QubitGyan API Documentation & Integration Guide

Welcome to the comprehensive API documentation for the QubitGyan EdTech platform. This guide serves as the implementation manual for both the **Next.js Student Application** and the **Next.js Admin Dashboard**.

---

## 🔐 1. Authentication & Base Setup

All API requests (except public endpoints like admissions and health checks) require a JWT Access Token.

* **Base API URL:** `https://your-domain.com/api/v1/`
* **Authorization Header:** `Authorization: Bearer <your_access_token>`

| Method | Endpoint | Description | Payload / Usage | Expected Response (200 OK) |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/token/` | Login & get tokens | `{"username": "...", "password": "..."}` | `{"access": "eyJ...", "refresh": "eyJ..."}` |
| **POST** | `/api/token/refresh/` | Refresh token | `{"refresh": "eyJ..."}` | `{"access": "new_token..."}` |

---

## ⚙️ 2. System Utilities & Globals
*Endpoints used for system health and global administrative features.*

### Health Check (Public)
* **GET** `/health/`
  * **Usage:** Used by hosting providers (Render/Vercel) to verify the server and database are alive.
  * **Response (200):** `{"status": "healthy", "database": "ok", "cache": "ok"}`

### Global Search (Admin)
* **GET** `/global-search/?q={query}`
  * **Usage:** Universal search bar in the Admin Panel. Searches nodes, resources, and users.
  * **Response (200):** `[{"type": "RESOURCE", "id": 12, "title": "Physics PDF", "url": "/admin/tree/1"}]`

### Admin Dashboard Stats (Admin)
* **GET** `/dashboard/stats/`
  * **Usage:** Populates the main charts and metrics on the Admin Dashboard.
  * **Response (200):** `{"counts": {"nodes": 45, "students": 120}, "charts": {...}, "recent_activity": [...]}`

---

## 🎓 3. Student Application API (`/public/`)
*Endpoints designed specifically for the student-facing Next.js frontend.*

### Admissions (No Auth Required)
* **POST** `/public/admissions/`
  * **Usage:** Student submits an application to join the platform. Triggers an automatic email.
  * **Payload:** `{"student_name": "Jane", "email": "jane@test.com", "phone": "1234", "class_grade": "10th"}`
  * **Response (201):** `{"id": 1, "status": "PENDING", ...}`

### Profile & Gamification
* **GET** `/public/my-profile/`
  * **Usage:** Fetch current student's basic details and avatar.
* **PUT** `/public/change-password/`
  * **Payload:** `{"old_password": "...", "new_password": "..."}`
* **GET** `/public/gamification/`
  * **Usage:** Dashboard stats for the student.
  * **Response (200):** `{"current_streak": 5, "longest_streak": 12, "total_learning_minutes": 450}`

### Courses & Enrollment
* **GET** `/public/courses/`
  * **Usage:** Browse all `is_published=True` courses.
* **GET** `/public/courses/my_courses/`
  * **Usage:** Fetch courses the student has actively enrolled in.
* **POST** `/public/courses/{id}/enroll/`
  * **Usage:** Add a course to the student's dashboard.
  * **Response (200):** `{"status": "Enrolled successfully"}`

### Taking Quizzes
* **GET** `/public/quizzes/{id}/`
  * **Usage:** Fetch a quiz and its questions. **Note:** The `is_correct` boolean is stripped from the payload to prevent cheating.
* **POST** `/public/quiz-attempts/submit/`
  * **Usage:** Submit a completed quiz. The backend calculates the score (handles negative marking).
  * **Payload:**
    ```json
    {
      "quiz_id": 1,
      "answers": [
        {"question_id": 10, "option_id": 42},
        {"question_id": 11, "option_id": 45}
      ]
    }
    ```
  * **Response (200):** `{"id": 5, "total_score": 1.5, "is_completed": true, "responses": [...]}`
* **GET** `/public/quiz-attempts/`
  * **Usage:** Fetch past attempt history and scores.

### Notifications
* **GET** `/public/notifications/`
  * **Usage:** Inbox for the student.
* **GET** `/public/notifications/unread_count/`
  * **Usage:** Fast, Redis-cached endpoint for the UI notification bell.
  * **Response (200):** `{"unread_count": 3}`
* **POST** `/public/notifications/mark_all_read/`
  * **Usage:** Clears the unread badge.

### Bookmarks & Resource Tracking
* **GET / POST / DELETE** `/bookmarks/`
  * **Payload (POST):** `{"resource": 15}`
* **GET / POST / PUT** `/progress/`
  * **Usage:** Track if a student has completed a video, PDF, or exercise.

---

## 🏗️ 4. Core Content Builder API (Admin Panel)
*Endpoints for building the curriculum. Requires `can_manage_content` permission.*

### Program Contexts
*Tags applied to resources (e.g., "TGT Exam", "PGT Exam", "Foundation").*
* **GET / POST / PUT / DELETE** `/contexts/`
  * **Payload (POST):** `{"name": "TGT Crash Course", "description": "Intensive prep."}`

### Knowledge Nodes (The Curriculum Tree)
*The hierarchical folders (Domain -> Subject -> Section -> Topic).*
* **GET** `/nodes/?depth=full`
  * **Usage:** Fetches the entire nested curriculum tree in one optimized, cached query.
* **POST** `/nodes/`
  * **Usage:** Create a new node.
  * **Payload:** `{"name": "Quantum Physics", "node_type": "TOPIC", "parent": 5, "order": 1}`
* **PUT / DELETE** `/nodes/{id}/`

### Resources (Content Files)
*The actual files (PDF, Video, Quiz, Exercise) attached to a Knowledge Node.*
* **GET** `/resources/?node={node_id}&type={PDF|VIDEO|QUIZ}`
  * **Usage:** Fetch resources inside a specific folder.
* **POST** `/resources/`
  * **Payload:** ```json
    {
      "title": "Newton's Laws",
      "resource_type": "PDF",
      "node": 12,
      "context_ids": [1, 2],
      "google_drive_link": "[https://drive.google.com/file/d/1A2B3C](https://drive.google.com/file/d/1A2B3C)..."
    }
    ```
* **POST** `/resources/reorder/`
  * **Usage:** Save Drag-and-Drop ordering from the frontend.
  * **Payload:** `{"ids": [15, 12, 18, 14]}`

---

## 🛡️ 5. Manager API (Admin Panel)
*High-level managerial functions. Prefixed with `/manager/`.*

### Admissions Processing (`can_approve_admissions`)
* **GET** `/manager/admissions/`
  * **Usage:** Review student applications.
* **POST** `/manager/admissions/{id}/approve/`
  * **Usage:** Creates the user account, generates a secure password, and queues a welcome email.
  * **Payload:** `{"remarks": "Verified school ID."}`
* **POST** `/manager/admissions/{id}/reject/`

### Quiz Creation & Management (`can_manage_content`)
* **GET / POST / PUT / DELETE** `/manager/quizzes/`
  * **Payload (POST):** `{"resource": 20, "passing_score_percentage": 60, "time_limit_minutes": 30}`
* **POST** `/manager/quizzes/{id}/add_question/`
  * **Usage:** Rapidly build a quiz by sending a question and its options in one payload.
  * **Payload:**
    ```json
    {
      "text": "What is the capital of France?",
      "marks_positive": 1.0,
      "marks_negative": 0.25,
      "options": [
        {"text": "Paris", "is_correct": true},
        {"text": "London", "is_correct": false}
      ]
    }
    ```

### Courses Wrapper (`can_manage_content`)
* **GET / POST / PUT / DELETE** `/manager/courses/`
  * **Usage:** Wraps a root Knowledge Node into a sellable/enrollable "Course".
  * **Payload (POST):** `{"title": "Physics 101", "description": "...", "root_node": 1, "is_published": true}`

### Media & Supabase Storage (Superadmin)
* **POST** `/manager/media/upload/`
  * **Usage:** Upload an image (Max 5MB). Send as `multipart/form-data`.
  * **Form Data:** `file` (Binary), `name` (String), `category` (e.g., 'thumbnails').
  * **Response (201):** `{"public_url": "https://...", "size_kb": 150}`
* **GET** `/manager/media/library/?category=thumbnails`
  * **Usage:** Browse uploaded images.
* **GET** `/manager/media/storage_status/`
  * **Usage:** See how much of the 1GB limit is used.
* **DELETE** `/manager/media/{id}/`
  * **Usage:** Safely deletes from both Supabase and the local database.

### Role-Based Access Control (Superadmin)
* **GET** `/manager/rbac/`
  * **Usage:** List all staff users and their current permissions.
* **PATCH** `/manager/rbac/{id}/update_permissions/`
  * **Payload:** ```json
    {
      "can_manage_content": true, 
      "can_approve_admissions": false,
      "can_manage_users": true
    }
    ```

### Email Queue System (Superadmin)
* **GET** `/manager/emails/`
  * **Usage:** Check the status of the asynchronous email queue (Pending/Sent/Failed).
* **POST** `/manager/emails/flush/`
  * **Usage:** Force the system to immediately send all pending emails.
  * **Response (200):** `{"status": "Attempted to send X emails", "sent": 2, "failed": 0}`

### Push Notifications (`IsSuperAdminOnly`)
* **GET / POST / DELETE** `/manager/notifications/`
  * **Usage:** Broadcast a message to all students, or target a specific user.
  * **Payload (POST):** `{"title": "System Maintenance", "message": "Down for 1 hour.", "target_user": null}` *(Leave `target_user` null for global broadcast).*