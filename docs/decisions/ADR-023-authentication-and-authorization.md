# ADR-023: Multi-User Authentication and Resource Authorization

**Status:** Accepted  
**Date:** 2026-09-08  
**Author:** RoadmapAI Engineering  
**Deciders:** Engineering Team  

---

## Context

RoadmapAI completed MVP-1 through MVP-7.2 as a single-user system. The FastAPI API adapter (MVP-7.2) exposed resource endpoints without authentication. To support multi-tenant production deployments safely, RoadmapAI requires robust multi-user identity and resource authorization while strictly maintaining backwards compatibility with local CLI single-user workflows and existing data.

### Key Requirements
1. **User Identity Boundary:** Distinct `User` account entity separate from `UserProfile` domain entity.
2. **Hard Invariant on Ownership:** `UserProfile.user_id` must be required, indexed, and enforced as a Foreign Key referencing `users.id`. Client cannot supply or forge `user_id`.
3. **Stateless Authentication:** Stateless JWT bearer access tokens with cryptographic signatures, strict algorithm whitelisting, and expiration validation.
4. **Timing-Safe Credentials:** Password hashing via `bcrypt` with salt rounds >= 12, timing attack mitigation during login (dummy hash verification for non-existent users), and generic rejection messages to prevent account enumeration.
5. **Discovery Protection Policy:** Cross-user resource lookups must return `404 RESOURCE_NOT_FOUND` rather than 403 Forbidden, making unauthorized resources completely indistinguishable from non-existent resources.
6. **Data Preservation & Single-User CLI Fallback:** Existing single-user databases must migrate smoothly without deleting data, orphaning records, or breaking existing CLI commands.

---

## Decision

### 1. Multi-User Domain and Storage Model

- **`User` Entity (`roadmap.domain.entities.user.py`):**
  Pure Python/Pydantic domain entity containing `id`, `email` (canonicalized/lowercase), `password_hash`, `status` ("active" | "suspended"), `created_at`, `updated_at`.
- **`UserModel` (`roadmap.storage.models.user_model.py`):**
  SQLAlchemy model mapping to `users` table with primary key `id: String(36)` and unique index on `email: String(255)`.
- **`UserProfileModel` (`roadmap.storage.models.user_profile_model.py`):**
  Hard Foreign Key: `user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)`.

### 2. Migration & Backfill Strategy (Alembic 0002)

To migrate single-user SQLite and PostgreSQL databases safely:
1. Create `users` table.
2. Bootstrap a deterministic legacy user (`legacy-local-user-000000000000`, `local@roadmap.ai`) if no users exist.
3. Backfill any existing `user_profiles` rows with `user_id = 'legacy-local-user-000000000000'`.
4. Apply NOT NULL constraint and Foreign Key reference using Alembic batch mode for SQLite compatibility.
5. In repository layer (`SqliteProfileRepository`), automatically ensure the legacy user exists when saving profiles without an explicit `user_id` (supporting local CLI single-user operations seamlessly).

### 3. Stateless Security Layer

- **Password Security (`roadmap.security.password.py`):**
  - Uses `bcrypt` for secure salted hashing.
  - Enforces password strength rules: minimum 8 characters, maximum 128 characters, requiring mixed character sets.
- **JWT Access Tokens (`roadmap.security.tokens.py`):**
  - Uses `pyjwt` with HMAC-SHA256 (`HS256`).
  - Strict algorithm allowlist on decode (`algorithms=[settings.auth_algorithm]`), rejecting the `none` algorithm and mismatched algorithms.
  - Payload claims: `sub` (user_id), `iat`, `nbf`, `exp` (default 60 minutes, configurable via `ROADMAP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`).
  - Production guard in `Settings`: `ROADMAP_AUTH_SECRET` must be explicitly configured (>= 32 characters, cannot contain "dev-insecure").

### 4. Canonical Dependency Providers (`roadmap.api.dependencies.py`)

- **`get_current_user`:**
  - Extracts Bearer token via `HTTPBearer(auto_error=False)`.
  - Missing token -> 401 `AUTHENTICATION_REQUIRED`.
  - Expired token -> 401 `TOKEN_EXPIRED`.
  - Invalid signature / malformed token -> 401 `INVALID_TOKEN`.
  - Resolves user from `SqliteUserRepository`; checks `user.is_active` -> 401 `INVALID_TOKEN` if inactive.
- **`get_authorized_profile`:**
  - Injects `profile_id: str` and `current_user: User = Depends(get_current_user)`.
  - Verifies `profile.user_id == current_user.id`.
  - If profile is missing OR belongs to another user -> raises `404 RESOURCE_NOT_FOUND`.

### 5. Protected Endpoint Surface

All profile-scoped endpoints depend on `get_authorized_profile`:
- Profiles: `GET /api/v1/profiles/{profile_id}`
- Profile Creation: `POST /api/v1/profiles` (binds strictly to `current_user.id`; client cannot provide `user_id`)
- Roadmaps: `GET /api/v1/profiles/{profile_id}/roadmaps`, `/latest`, `/{version}`
- Progress: `GET/POST /api/v1/profiles/{profile_id}/progress`
- Feedback: `POST /api/v1/profiles/{profile_id}/feedback`
- Adaptations: `POST /api/v1/profiles/{profile_id}/adaptations/prepare`
- Knowledge: `GET /api/v1/profiles/{profile_id}/knowledge/search`

---

## Consequences

### Positive
- **Complete Multi-User Isolation:** No user can access or modify another user's profiles, roadmaps, progress, feedback, adaptations, or knowledge searches.
- **Discovery Protection:** Attackers cannot enumerate resource IDs; 404 responses for missing and unauthorized resources are indistinguishable.
- **Timing Attack Resistance:** Dummy hash execution prevents side-channel username enumeration.
- **Backward Compatibility:** Existing CLI single-user workflows and legacy SQLite databases operate uninterrupted without requiring auth headers.
- **Deterministic Schema:** Hard foreign key and non-null column enforce relational integrity at the database engine level.

### Negative / Trade-offs
- Every API test for protected resources must provide valid authorization headers.
- JWT access tokens are stateless; immediate token revocation before expiration requires adding a token blacklist or refresh-token rotation in a future milestone.

---

## Verification

1. **Unit & API Tests:**
   - `tests/api/test_auth.py`: 14 tests verifying registration, duplicate email handling, case insensitivity, password strength, login, timing safety, token decoding, and expiration.
   - `tests/api/test_authorization.py`: 10 tests verifying cross-user authorization across all 6 resource families, client parameter tampering immunity, single-profile limit, and unauthenticated rejections.
2. **Regression Suite:** 288 total tests passing across domain, application, storage, CLI, and API layers.
3. **Database Migration:** Alembic migration `0002_add_user_auth` verified against existing `roadmap.db`.
4. **Type Safety & Linting:** 100% clean across Ruff and Mypy (180 source files checked, 0 errors).
