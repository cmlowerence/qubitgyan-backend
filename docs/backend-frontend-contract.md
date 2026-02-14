# Backend → Frontend Integration Map (v2.0 - LMS Upgrade)

This file maps the current Django + DRF backend behavior so the Next.js frontend can reliably integrate against the existing API.

Base API prefix: `/api/v1/`
Auth endpoints: `/api/token/`, `/api/token/refresh/`

---

## 1) Authentication & Access Model

### Auth flow (JWT)
- **Login**: `POST /api/token/`
  - Input: `username` (Note: This is the user's **email address**), `password`
  - Output: `access`, `refresh`
- **Refresh token**: `POST /api/token/refresh/`
  - Input: `refresh`
  - Output: `access`
- **Change Password**: `PUT /api/v1/public/change-password/`
  - Input: `old_password`, `new_password` (Requires Bearer Token)

### Permission defaults & RBAC (Role-Based Access Control)
- **Students**: Require standard `IsAuthenticated` token.
- **Standard Admins**: Require `is_staff=True`. Can only edit content if their `UserProfile` has `can_manage_content=True`. Can only approve students if `can_approve_admissions=True`.
- **Superadmins**: Require `is_superuser=True`. Full access to all endpoints, including RBAC toggles and Supabase media deletion.

---

## 2) Core Data Model (Frontend-relevant Additions)

### Course & Enrollment
- **Course**: A publishable wrapper around a top-level `KnowledgeNode`. Includes `id`, `title`, `description`, `thumbnail_url`, `is_published`, `root_node` (id), and `is_enrolled` (computed boolean).
- **Enrollment**: Links a `User` to a `Course`.

### Gamification & Profile (UserProfile projection)
- Profiles now contain LMS stats: `current_streak`, `longest_streak`, `total_learning_minutes`, `last_active_date`, and `avatar_url`.

### Admissions
- **AdmissionRequest**: `id`, `student_name`, `email`, `phone_number`, `status` (`PENDING`, `APPROVED`, `REJECTED`), `review_remarks`.

### Quizzes
- **Quiz**: Attached to a `Resource` of type `QUIZ`. Contains `passing_score_percentage`, `time_limit_minutes`.
- **Questions & Options**: Deeply nested. *Note: Correct answers (`is_correct`) are stripped from the payload when fetched by students.*

### Notifications & Bookmarks
- **Notification**: `id`, `title`, `message`, `target_user` (nullable for global blasts), `is_read` (computed).
- **Bookmark**: Links a `User` to a `Resource` for "Watch Later" functionality.

### Progress & Tracking
- **StudentProgress**: Now includes `resume_timestamp` (integer in seconds) to remember exactly where a student paused a video.

---

## 3) Endpoint Map and Frontend Usage

### 3.1 Core Contract (The Library)
- **Nodes**: `GET /api/v1/nodes/` (Returns root nodes + nested children).
- **Resources**: `GET /api/v1/resources/?node=<id>` (Returns resources for a specific node).
- **Progress**: `GET /api/v1/progress/` (Student's completed resources).
- **Contexts**: `GET /api/v1/contexts/` (Taxonomy/Tags).

### 3.2 Public Endpoints (Student-Facing)
Prefix: `/api/v1/public/`

- **Admissions**
  - `POST admissions/`: Submit a new application form (Rate limited).
- **Profile & Gamification**
  - `GET my-profile/`: Fetch the logged-in student's stats and streak.
  - `POST gamification/ping/`: Call every 5 minutes while active. Body: `{"minutes": 5}`.
- **Courses**
  - `GET courses/`: Browse all published courses.
  - `POST courses/:id/enroll/`: Add course to student's library.
  - `GET courses/my_courses/`: Fetch only enrolled courses.
- **Quizzes**
  - `GET quizzes/`: Fetch quiz data (WITHOUT correct answers).
  - `POST quiz-attempts/`: Submit selected option IDs. Backend calculates score and returns pass/fail.
  - `GET quiz-attempts/`: View past scores.
- **Bookmarks & Tracking**
  - `CRUD bookmarks/`: Save/remove resources for later.
  - `POST tracking/save_timestamp/`: Save video playback position. Body: `{"resource_id": 1, "resume_timestamp": 120}`.
- **Notifications**
  - `GET notifications/`: Fetch inbox.
  - `POST notifications/:id/mark_read/`: Mark as seen.

### 3.3 Manager Endpoints (Admin-Facing)
Prefix: `/api/v1/manager/`

- **Admissions**
  - `GET admissions/`: List all applications.
  - `PATCH admissions/:id/process_application/`: Approve/Reject. If APPROVED, auto-creates user and queues the email. Body: `{"status": "APPROVED"}`.
- **Courses & Quizzes**
  - `CRUD courses/`: Build course wrappers.
  - `CRUD quizzes/`: Create quizzes using deeply nested JSON (Resource -> Quiz -> Questions -> Options).
- **Email Queue**
  - `GET emails/queue_status/`: See pending/sent counts.
  - `POST emails/dispatch_batch/`: Safely send emails via Gmail SMTP to avoid spam blocks. Body: `{"limit": 20}`.
- **Media Storage (Supabase)**
  - `POST media/upload/`: Upload images. Uses `multipart/form-data`.
  - `GET media/storage_status/`: Check 1GB bucket limit.
  - `DELETE media/:id/` *(Superadmin Only)*: Deletes from DB and frees Supabase storage.
- **RBAC Security**
  - `GET rbac/list_admins/` *(Superadmin Only)*: View staff permissions.
  - `PATCH rbac/:id/update_permissions/` *(Superadmin Only)*: Toggle `can_manage_content`, etc.

---

## 4) Response Shapes (New Key Payloads)

### 4.1 Gamification Ping
`POST /api/v1/public/gamification/ping/`
```json
{
  "current_streak": 3,
  "longest_streak": 12,
  "total_learning_minutes": 450
}