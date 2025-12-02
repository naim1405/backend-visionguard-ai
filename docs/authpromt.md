You are a senior backend engineer. Design and implement a clean, secure authentication and authorization system for an application called **VisionGuard AI**.

## Tech Stack (MANDATORY)

- Programming language: **Python**
- Database: **PostgreSQL**
- ORM: **SQLAlchemy** (use SQLAlchemy ORM, not raw SQL for main logic)
- Migrations: You may assume **Alembic** for schema migrations.
- Web framework: You may choose **FastAPI** or **Flask**, but design your solution so it is easy to adapt to either.
- Auth: **JWT**-based authentication.
- Password hashing: Use a strong hashing algorithm (e.g. `bcrypt` via `passlib` or similar).

Make your answer self-contained and Python-focused, using SQLAlchemy models and typical patterns for a production-grade Python backend.

---

## Context

VisionGuard AI currently:

- Runs locally.
- Connects to CCTV cameras of shops.
- Performs **real-time anomaly detection** on CCTV footage.

Right now there is **no authentication or authorization** — everything is open. I want you to design and (if possible) provide implementation details for a proper backend that adds auth + role-based access control, while integrating cleanly with the existing functionality.

---

## Core Requirements

### 1. User & Roles

There are only **two roles**:

- `OWNER`
- `MANAGER`

A **User** must have at least:

- `id` (UUID or numeric)
- `name`
- `email` (unique, required)
- `password_hash` (hashed password, never store plain text)
- `role` (`OWNER` or `MANAGER`)
- timestamps: `created_at`, `updated_at`

Rules:

- An **Owner** can have **multiple shops**.
- A **Manager** can only access **one or more specific shops** they are assigned to, not all shops of the owner.
- Authentication is **email + password** based.
- An **Owner** can add one or more managers **using their email**.
- An account’s role is fixed at creation time (no arbitrary role switching via API unless explicitly allowed in an admin-only endpoint).

### 2. Shop Model

A **Shop** should have at least:

- `id`
- `owner_id` (FK to User with role OWNER)
- `name`
- `address`
- `created_at`, `updated_at`

Additionally:

- Shops have **assigned managers**, represented as an array of **emails** in the create/update payload.
- On the backend, model manager assignment as a **many-to-many relation**:
  - Table such as `shop_managers` with:
    - `id`
    - `shop_id` (FK to shops)
    - `manager_id` (FK to users with role MANAGER)

Behavior when creating/updating a shop:

- In the **Add Shop** API, the payload includes `assigned_manager_emails: List[str]`.
- For each email:
  - If a user with that email and role MANAGER already exists:
    - Link them to that shop in `shop_managers`.
  - If no user exists with that email:
    - Create a **manager** user with that email, role `MANAGER`, and:
      - Either a randomly generated temporary password, or
      - A status that requires them to finish registration (depending on your design).
    - Link them to that shop.
- Optionally: describe how an email invitation flow would work, but don’t rely on it being implemented right now.

### 3. Authentication Flow (Python + JWT)

Implement **email + password authentication** in Python:

- Passwords must be stored using a strong hashing algorithm like **bcrypt** (e.g. via `passlib`).
- Provide endpoints such as:
  - `POST /auth/register-owner`
    - Create a new OWNER account.
    - Payload: `name`, `email`, `password`.
    - Should reject if email is already taken.
  - `POST /auth/login`
    - Payload: `email`, `password`.
    - On success, returns:
      - A **JWT access token** (include user id and role).
      - Optionally, a refresh token or session mechanism.

Token contents (for JWT):

- `sub`: user id
- `role`: user role (`OWNER` or `MANAGER`)
- `email`: user email
- Standard fields like `iat`, `exp`.

Make sure to:

- Set a reasonable token expiration time.
- Show Python code for token generation and verification (using a library like `pyjwt` or equivalent).
- Explain how to validate tokens in a middleware / dependency (depending on Flask vs FastAPI).
- Explain where to store secrets (e.g., `JWT_SECRET` in environment variables).

### 4. Authorization Rules (RBAC)

Implement middleware-based authorization that:

- **Protects all VisionGuard AI APIs** behind authentication, especially:
  - Any endpoint that returns shop details.
  - Any endpoint that exposes CCTV streams / anomaly detection results per shop.

Middleware responsibilities:

1. **Authentication middleware**:

   - Extract JWT from `Authorization: Bearer <token>`.
   - Verify and decode JWT.
   - Attach decoded user info (id, role, email) to the request context (e.g. `request.state.user` or a FastAPI dependency).

2. **Authorization middleware/guards**:
   - `require_role('OWNER')`:
     - Only allow users with role OWNER.
   - `require_role('MANAGER')`:
     - Only allow MANAGER.
   - `require_shop_access(shop_id)`:
     - If user is OWNER:
       - Check that `shop.owner_id == user.id`.
     - If user is MANAGER:
       - Check that user is in `shop_managers` for that `shop_id`.
     - Otherwise deny with 403.

Ensure:

- A MANAGER **only sees the shops they are assigned to**.
- An OWNER **only sees/manages their own shops**, not other owners’ shops.

### 5. API Design (Python)

Propose and document a REST-style API. For example:

#### Auth

- `POST /auth/register-owner`
- `POST /auth/login`
- `POST /auth/logout` (if using server-side sessions or refresh tokens)

#### Shops (OWNER only where specified)

- `POST /shops`
  - Create a shop for the authenticated OWNER.
  - Payload: `name`, `address`, `assigned_manager_emails: List[str]`.
- `GET /shops`
  - If OWNER: list all shops owned by this owner.
- `GET /shops/:id`
  - OWNER: only if they own it.
  - MANAGER: only if assigned to it.
- `PUT /shops/:id`
  - OWNER only; can update name, address, assigned_manager_emails.
- `DELETE /shops/:id`
  - OWNER only.

#### Manager View

- `GET /my/shops`
  - If MANAGER: return only shops they are assigned to.
  - If OWNER: return shops they own.

#### Manager Management (OWNER only)

- `POST /managers`
  - Optionally create managers independently of shops.
- `GET /managers`
  - List managers under this owner (if you choose to model owner-manager link beyond shops).
- `PUT /shops/:id/managers`
  - Update manager assignments by email array.

Provide example request/response bodies in JSON.

### 6. Integration With Existing VisionGuard Functionality

Assume there is already a module/service that:

- Connects to CCTV camera streams.
- Runs anomaly detection.
- Exposes some internal APIs or functions like:
  - `GET /shops/:id/stream`
  - `GET /shops/:id/anomalies`
  - Or WebSocket endpoints for live events.

Your job:

- **Do not change the core detection logic**, but **wrap it** behind the new auth layer.
- For any endpoint that deals with a specific shop:
  - Use the `require_shop_access(shop_id)` authorization check described above.
- If you design WebSocket endpoints, explain how auth is performed in Python (e.g., token in query param or WebSocket headers, validated on connection).

### 7. Database Schema (PostgreSQL + SQLAlchemy)

Provide a clean database schema using **PostgreSQL** and **SQLAlchemy ORM models** for at least:

- `users`
- `shops`
- `shop_managers` (junction table)

Example fields:

- `users`:
  - `id`, `name`, `email`, `password_hash`, `role`, `created_at`, `updated_at`.
- `shops`:
  - `id`, `owner_id`, `name`, `address`, `created_at`, `updated_at`.
- `shop_managers`:
  - `id`, `shop_id`, `manager_id`, `created_at`, `updated_at`.

Explain and/or show:

- SQLAlchemy `Base` models for these tables.
- Relationships between models (`relationship`, `back_populates`).
- Indexes that should exist (e.g., unique on `email`, composite index on `shop_id, manager_id`).
- Foreign key constraints.
- How migrations would be handled conceptually with Alembic (you don’t need to write full migration scripts, but outline the approach).

### 8. Security Best Practices (Python)

Explicitly describe and/or implement:

- Password hashing with salt using a Python library (e.g. `passlib.hash.bcrypt`).
- Input validation (e.g. using Pydantic if FastAPI, or marshmallow/other library for Flask).
- Rate limiting strategy for auth endpoints (high-level description is enough).
- How to store secrets (JWT secret, DB password) in environment variables and load them in Python.
- CORS considerations if frontend is separate.
- Error handling: meaningful but not leaking sensitive info (e.g., generic “Invalid credentials” instead of revealing whether email exists).

---

## Output Format

In your answer, please include:

1. **High-level architecture description** – how components (API, DB, detection service) interact, specifically in a Python + PostgreSQL + SQLAlchemy context.
2. **Database schema** – SQLAlchemy ORM model definitions and explanation of the tables.
3. **API endpoint definitions** – paths, methods, example request/response bodies.
4. **Sample Python code snippets** for:
   - User registration (OWNER).
   - Login and JWT issuance.
   - Auth middleware/dependency.
   - A protected endpoint that returns shops visible to the logged-in user (showing both OWNER and MANAGER behavior).
5. A short **explanation of how a typical flow works**:
   - Owner registers → logs in → creates shops → assigns managers → manager logs in → sees only assigned shops → accesses anomaly detection for those shops.

Design everything in a way that is clean, modular, and production-ready so I can extend it later (e.g., adding more roles or permissions).
