# URL Shortener Flask Web API — Design Spec

## Summary

Extend the existing CLI-based URL shortener with a Flask web API. The web server provides HTTP endpoints for shortening URLs, redirecting visitors (with click tracking), optional link expiry via TTL, multi-user authentication with per-user API keys, manual rate limiting, and a basic analytics dashboard.

## Architecture

### File Organization

| File | Purpose |
|------|---------|
| `database.py` | Shared module: DB connection, schema setup/migration, base62 encoding, URL validation, all CRUD operations, user authentication functions |
| `main.py` | CLI tool — unchanged behavior, imports shared logic from `database.py` |
| `app.py` | Flask web server — imports shared logic from `database.py` |
| `requirements.txt` | Single dependency: `flask` |
| `flask_explanation.md` | Line-by-line walkthrough of `app.py` and new `database.py` functions |

### Relationship Between CLI and Web Server

Two separate tools that share the same SQLite database file (`urls.db`). Either can be run independently. Running both at the same time is fine — SQLite handles concurrent reads, and write contention is negligible at this scale.

- CLI: `python main.py <command>`
- Web: `python app.py` (starts server on `http://localhost:5000`)

### Short Code Generation

Counter + Base62 encoding (existing approach, inherently collision-free). No hash-based generation.

### Why Not Hash-Based?

Hashing the URL (MD5/SHA256 + truncation) introduces collisions that need detection and retry logic. The counter approach guarantees uniqueness by assigning each URL a sequential number and converting it to Base62. This is what Bitly uses in production. We keep it.

---

## Database Schema

All tables and columns are created upfront by `setup_database()`. This avoids ALTER TABLE migrations across phases. Columns added for later phases sit unused (nullable) until the phase that needs them.

```sql
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_custom INTEGER NOT NULL DEFAULT 0,
    click_count INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    user_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_short_code ON urls (short_code);

CREATE TABLE IF NOT EXISTS counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_value INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);
```

### Migration from Existing CLI Database

For users upgrading from the CLI-only version (whose `urls` table lacks `click_count`, `expires_at`, `user_id`): `setup_database()` uses `PRAGMA table_info(urls)` to detect missing columns and adds them via `ALTER TABLE`. Existing shortened URLs are preserved.

---

## API Endpoints

### Public (no auth)

| Method | Path | Description | Success |
|--------|------|-------------|---------|
| GET | `/<code>` | Redirect to original URL, increment click count | 302 redirect |
| POST | `/register` | Create new user account | 201 + API key |
| POST | `/login` | Authenticate, get API key | 200 + API key |

### Authenticated (requires `X-API-Key` header)

| Method | Path | Description | Request Body | Success |
|--------|------|-------------|-------------|---------|
| POST | `/shorten` | Create short URL | `{"url", "alias"?, "ttl_seconds"?}` | 201 + short code |
| GET | `/stats/<code>` | Click count, created_at, original URL | — | 200 + JSON |
| DELETE | `/<code>` | Delete a short URL | — | 200 + confirmation |
| GET | `/analytics` | Top 5 most-clicked links (HTML) | — | 200 + HTML |

### Error Responses

| Code | Meaning | When |
|------|---------|------|
| 400 | Bad Request | Missing fields, invalid URL, invalid alias characters, reserved alias name |
| 401 | Unauthorized | Missing or invalid API key, wrong login credentials |
| 404 | Not Found | Short code doesn't exist |
| 409 | Conflict | Alias already taken, username already taken |
| 410 | Gone | Link has expired (TTL elapsed) |
| 429 | Too Many Requests | Rate limit exceeded |

---

## Authentication Model

### Phase 2 (before users exist)

Simple environment variable check. User sets `API_KEY=somesecret` before running the server. The `DELETE` endpoint checks `X-API-Key` header against this env var. If no env var is set, `DELETE` works without auth.

### Phase 3 (multi-user)

Per-user API keys stored in the `users` table. Generated on registration via `secrets.token_hex(32)` (64-char hex string). Returned on login. Required in `X-API-Key` header for all write/delete/stats/analytics operations. Replaces the env var mechanism.

### Password Security

- `hashlib.pbkdf2_hmac("sha256", ...)` with 100,000 iterations
- Random 16-byte salt per password via `secrets.token_hex(16)`
- Stored as `"salt:hash"` string in `password_hash` column
- All stdlib — no bcrypt or external packages

---

## TTL Expiry

- Optional `ttl_seconds` integer on `POST /shorten`
- Converted to `expires_at` ISO timestamp: `now + ttl_seconds`
- Checked at request time in `GET /<code>` and `GET /stats/<code>`
- If expired: row is immediately deleted from database, response is `410 Gone`
- Links without `ttl_seconds` never expire (`expires_at` is NULL)

---

## Rate Limiting

- In-memory sliding window: dictionary mapping IP → list of request timestamps
- Applied only to `POST /shorten`
- Default limit: 10 requests per IP per 60-second window
- Old timestamps are pruned on each check
- Returns `429 Too Many Requests` with error message when exceeded
- Resets on server restart (acceptable — this is a portfolio project, not production)

---

## Reserved Route Names

Custom aliases are validated against a set of reserved names to prevent conflicts with API routes:

```python
RESERVED_ROUTE_NAMES = {"shorten", "register", "login", "stats", "analytics"}
```

If a user tries `--alias analytics`, they get an error. Auto-generated codes (Base62 from counter) cannot collide with these since they start at counter value 100,000 (`q0U`).

---

## Phase Breakdown

| Phase | Scope | What It Accomplishes |
|-------|-------|---------------------|
| 1 | Extract `database.py`, create `app.py` with 4 core endpoints, click counting | Working web API: shorten, redirect, stats, delete |
| 2 | TTL expiry, env-var API key auth on DELETE | Links can expire, DELETE is protected |
| 3 | User registration/login, per-user API keys, user-scoped data | Multi-user system with data isolation |
| 4 | Rate limiting, analytics dashboard, documentation | Polish, documentation, final deliverables |

Each phase ends with a verification checkpoint: curl tests, CLI regression check, and code simplicity review.
