# Backend → Frontend Integration Map

This file maps the current Django + DRF backend behavior so frontend can reliably integrate against the existing API.

Base API prefix: `/api/v1/`
Auth endpoints: `/api/token/`, `/api/token/refresh/`

---

## 1) Authentication & Access Model

## Auth flow (JWT)
- **Login**: `POST /api/token/`
  - Input: `username`, `password`
  - Output: `access`, `refresh`
- **Refresh token**: `POST /api/token/refresh/`
  - Input: `refresh`
  - Output: `access`

### Permission defaults
- Global default requires authentication (`IsAuthenticated`).
- Most content endpoints use custom `IsAdminOrReadOnly`:
  - `GET/HEAD/OPTIONS` are public/readable.
  - write actions require `is_staff=True`.
- Some endpoints are admin-only (`IsAdminUser`) and must be called by staff users.

---

## 2) Core Data Model (Frontend-relevant)

## KnowledgeNode (tree)
Represents hierarchy for learning tree:
- `id`
- `name`
- `node_type` ∈ `DOMAIN | SUBJECT | SECTION | TOPIC`
- `parent` (nullable id)
- `order`
- `thumbnail_url`
- `is_active`

Computed in serializers:
- `resource_count`: number of resources directly linked to this node
- `items_count`: number of immediate child nodes
- `children`: nested children array (recursive, same shape)

## Resource
Learning content attached to a node:
- `id`, `title`
- `resource_type` ∈ `PDF | VIDEO | QUIZ | EXERCISE`
- `node` (id), `node_name`
- `contexts` (expanded objects)
- `context_ids` (write-only list of context ids)
- `google_drive_id`, `google_drive_link` (write-only helper)
- `external_url`, `content_text`
- `preview_link` (computed)
- `created_at`, `order`

## ProgramContext
Grouping/taxonomy for resources:
- `id`, `name`, `description`

## StudentProgress
Per-user completion tracking:
- `id`, `resource`, `is_completed`, `last_accessed`
- one unique row per `(user, resource)`

## User (+ profile projection)
User response includes profile-projected fields:
- Django user fields: `id`, `username`, `email`, `first_name`, `last_name`, `is_staff`, `is_superuser`
- profile-derived: `created_by`, `avatar_url`, `is_suspended`

---

## 3) Endpoint Map and Frontend Usage

## 3.1 Nodes (knowledge tree)
Base: `/api/v1/nodes/`

### GET `/api/v1/nodes/`
Returns **top-level nodes only** (`parent = null`) with recursive `children` nested down the full tree.

Query params:
- `search=<text>`: text search on name
- `all=true`: returns all nodes (not only root)

### GET `/api/v1/nodes/:id/`
Returns one node with nested `children`.

### POST/PATCH/DELETE `/api/v1/nodes/...`
Write access is admin/staff only.

---

## 3.2 Resources
Base: `/api/v1/resources/`

### GET `/api/v1/resources/`
Supports filters:
- `node=<nodeId>` → resources for node, ordered by `order`
- `type=<PDF|VIDEO|QUIZ|EXERCISE|ALL>`
- `context=<contextId|ALL>`
- `search=<text>` across title/context/node

Default ordering (when not filtering by `node`): newest first.

### POST `/api/v1/resources/`
Use `context_ids` for writing contexts and optional `google_drive_link` helper.

### POST `/api/v1/resources/reorder/`
Admin only. Body:
```json
{ "ids": [11, 7, 9] }
```
Sets `order` by array position.

---

## 3.3 Contexts
Base: `/api/v1/contexts/`
- Standard CRUD
- Reads are public
- Writes are admin/staff only

---

## 3.4 Users
Base: `/api/v1/users/` (admin-only endpoint)

### GET `/api/v1/users/`
- Superuser sees all users.
- Staff admin (non-superuser) sees only students (`is_staff=false`).

### POST `/api/v1/users/`
- Superuser can create admin/superuser accounts.
- Non-superuser admin is blocked from setting privileged flags.

### PATCH `/api/v1/users/:id/`
- Superuser can change `is_staff` / `is_superuser`.
- Non-superuser admin cannot alter privilege flags.

### GET `/api/v1/users/me/`
Authenticated user endpoint returning own user payload + profile projection.

---

## 3.5 Student Progress
Base: `/api/v1/progress/`

### GET `/api/v1/progress/`
Authenticated user sees **only own** progress rows.

### POST `/api/v1/progress/`
`user` is auto-assigned from token; frontend only sends resource/completion fields.

### GET `/api/v1/progress/all_admin_view/`
Admin-only aggregate view of all students.

---

## 3.6 Dashboard + Search

### GET `/api/v1/dashboard/stats/` (admin only)
Returns counters, charts, and recent resources.

### GET `/api/v1/global-search/?q=<text>` (admin only)
Returns mixed result items (`NODE`, `RESOURCE`, `USER`).

---

## 4) Response Shapes (Samples)

> Note: List responses are paginated by DRF globally. Typical shape is:
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/nodes/?page=2",
  "previous": null,
  "results": []
}
```

## 4.1 Login
`POST /api/token/`

Response:
```json
{
  "refresh": "<jwt_refresh_token>",
  "access": "<jwt_access_token>"
}
```

## 4.2 Nodes list (root + deep children)
`GET /api/v1/nodes/`

Response:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Mathematics",
      "node_type": "DOMAIN",
      "parent": null,
      "order": 1,
      "thumbnail_url": null,
      "is_active": true,
      "children": [
        {
          "id": 2,
          "name": "Algebra",
          "node_type": "SUBJECT",
          "parent": 1,
          "order": 1,
          "thumbnail_url": null,
          "is_active": true,
          "children": [
            {
              "id": 3,
              "name": "Linear Equations",
              "node_type": "SECTION",
              "parent": 2,
              "order": 1,
              "thumbnail_url": null,
              "is_active": true,
              "children": [
                {
                  "id": 4,
                  "name": "Elimination Method",
                  "node_type": "TOPIC",
                  "parent": 3,
                  "order": 1,
                  "thumbnail_url": null,
                  "is_active": true,
                  "children": [],
                  "resource_count": 2,
                  "items_count": 0
                }
              ],
              "resource_count": 0,
              "items_count": 1
            }
          ],
          "resource_count": 0,
          "items_count": 1
        }
      ],
      "resource_count": 0,
      "items_count": 1
    }
  ]
}
```

## 4.3 Resource item
`GET /api/v1/resources/?node=4`

Response example item:
```json
{
  "id": 10,
  "title": "Intro PDF",
  "resource_type": "PDF",
  "node": 4,
  "node_name": "Elimination Method",
  "contexts": [{ "id": 1, "name": "JEE", "description": "Engineering prep" }],
  "google_drive_id": "1AbCdEfGhIjKlMnOpQrStUvWx",
  "external_url": null,
  "content_text": null,
  "preview_link": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWx/preview",
  "created_at": "2026-02-12T10:14:58.221Z",
  "order": 0
}
```

## 4.4 Student progress list
`GET /api/v1/progress/`

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "resource": 10,
      "is_completed": true,
      "last_accessed": "2026-02-12T11:40:21.101Z"
    }
  ]
}
```

## 4.5 Dashboard stats
`GET /api/v1/dashboard/stats/`

```json
{
  "counts": {
    "nodes": 124,
    "admins": 3,
    "students": 250,
    "resources": 890
  },
  "charts": {
    "distribution": [
      { "resource_type": "PDF", "count": 420 },
      { "resource_type": "VIDEO", "count": 300 }
    ],
    "top_subjects": [
      { "name": "Coordinate Geometry", "resource_count": 80 }
    ]
  },
  "recent_activity": [
    {
      "id": 101,
      "title": "Circle Notes",
      "resource_type": "PDF",
      "node": 18,
      "node_name": "Circles",
      "contexts": [],
      "google_drive_id": "1xxxyyyzzz",
      "external_url": null,
      "content_text": null,
      "preview_link": "https://drive.google.com/file/d/1xxxyyyzzz/preview",
      "created_at": "2026-02-12T08:00:00Z",
      "order": 0
    }
  ]
}
```

## 4.6 Global search
`GET /api/v1/global-search/?q=alg`

```json
[
  {
    "type": "NODE",
    "id": 2,
    "title": "Algebra",
    "subtitle": "Type: SUBJECT",
    "url": "/admin/tree/2"
  },
  {
    "type": "RESOURCE",
    "id": 10,
    "title": "Algebra Basics PDF",
    "subtitle": "File: PDF",
    "url": "/admin/tree/2"
  },
  {
    "type": "USER",
    "id": 41,
    "title": "student_rahul",
    "subtitle": "rahul@example.com",
    "url": "/admin/users"
  }
]
```

---

## 5) Frontend Implementation Notes (Important)

- **Always parse paginated list responses via `results`**.
- **Tree traversal** should recurse through `node.children` until empty array.
- Resource write requests should use `context_ids`, not `contexts`.
- For PDF display, use `preview_link` when present.
- Progress endpoints are user-scoped unless using admin aggregate endpoint.
- User management screens should assume role-based field restrictions (some updates can return 403 for non-superusers).

---

## 6) Suggested quick API checklist for frontend

1. Login and store access/refresh.
2. Fetch `/api/v1/nodes/`, render nested tree from `results[].children` recursively.
3. On node click, fetch `/api/v1/resources/?node=<id>`.
4. Track completion through `/api/v1/progress/`.
5. For admin app: use dashboard, global search, reorder endpoint, and user endpoint with role-aware handling.
