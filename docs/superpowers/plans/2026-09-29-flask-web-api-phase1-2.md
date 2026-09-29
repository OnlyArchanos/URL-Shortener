# Flask Web API — Implementation Plan (Phases 1-2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the CLI-based URL shortener with a Flask web API supporting shortening, redirection with click tracking, TTL expiry, multi-user auth, rate limiting, and analytics.

**Architecture:** Extract shared database/encoding/validation logic into `database.py`. Keep `main.py` as the CLI (importing from `database.py`). Create `app.py` as the Flask web server (also importing from `database.py`). Build features incrementally across 4 phases.

**Tech Stack:** Python 3.6+, Flask (only external dependency), SQLite (stdlib `sqlite3`), `hashlib`/`secrets` for password hashing and key generation.

**Spec:** `docs/superpowers/specs/2026-09-29-flask-web-api-design.md`

## Global Constraints

- Zero comments in code. No `#` notes, no docstrings. Code speaks through naming and structure.
- Code must not look AI-generated. Descriptive variable names (2-3 words minimum), action-oriented function names, no single-letter variables.
- Flask is the only allowed external package. Everything else uses Python stdlib.
- All SQL uses parameterized queries with `?` placeholders.
- Functions stay under ~30 lines. Blank lines between logical sections.
- Commit messages are short, lowercase, casual.
- Each phase ends with a verification checkpoint before proceeding.

---

# Phase 1: Foundation

Extract shared logic, create Flask app with core endpoints.

**What this accomplishes:** A working web API where you can shorten URLs via HTTP, follow short links (with click counting), check stats, and delete links. The CLI continues to work exactly as before.

---

### Task 1: Create `database.py` and Update `main.py`

**Files:**
- Create: `database.py`
- Modify: `main.py`

**Interfaces:**
- Consumes: Nothing (this is the foundation)
- Produces: All shared functions that `main.py` and `app.py` (Task 2) import:
  - `setup_database()` — creates/migrates all tables
  - `get_database_connection()` — returns `sqlite3.Connection` with `row_factory = sqlite3.Row`
  - `convert_number_to_base62(decimal_number)` — returns `str`
  - `get_next_short_code(database_connection)` — returns `str`, increments counter (does NOT commit)
  - `check_if_url_is_valid(url_string)` — returns `bool`
  - `validate_custom_alias(alias_text, database_connection)` — returns error `str` or `None`
  - `save_url_to_database(database_connection, short_code, original_url, is_custom_alias, ttl_seconds=None, user_id=None)` — does NOT commit
  - `find_url_by_short_code(database_connection, short_code)` — returns `sqlite3.Row` or `None`
  - `delete_url_from_database(database_connection, short_code)` — does NOT commit
  - `increment_click_count(database_connection, short_code)` — does NOT commit
  - `get_all_urls(database_connection, user_id=None)` — returns `list[sqlite3.Row]`

---

- [ ] **Step 1: Create `database.py` with all shared functions**

Create `database.py` in the project root. It contains ALL functions listed above, moved from `main.py`, plus new ones (`find_url_by_short_code`, `delete_url_from_database`, `increment_click_count`, `get_all_urls`, `get_existing_column_names_for_urls`).

Key additions vs the old `main.py`:
- `RESERVED_ROUTE_NAMES = {"shorten", "register", "login", "stats", "analytics"}` — prevents custom aliases from conflicting with API routes
- `validate_custom_alias` now checks against reserved names
- `save_url_to_database` gains optional `ttl_seconds` and `user_id` params (unused until Phases 2 and 3)
- `setup_database()` creates the full schema (urls with `click_count`, `expires_at`, `user_id` columns + users table + counter table) and handles migration from old CLI databases via `PRAGMA table_info` + `ALTER TABLE`
- `from datetime import timedelta` added for TTL calculation

The complete code for `database.py` is in the spec appendix. Every function follows the project rules: no comments, descriptive names, parameterized SQL, under 30 lines each.

---

- [ ] **Step 2: Update `main.py` — remove extracted functions, add imports**

Replace lines 1-143 of `main.py` (all imports + constants + extracted functions) with:

```python
import sys
import argparse
from database import (
    setup_database,
    get_database_connection,
    get_next_short_code,
    check_if_url_is_valid,
    validate_custom_alias,
    save_url_to_database,
    find_url_by_short_code,
    delete_url_from_database,
    get_all_urls
)
```

Update `handle_resolve_command` to use `find_url_by_short_code()` instead of inline SQL.
Update `handle_list_command` to use `get_all_urls()` instead of inline SQL.
Update `handle_delete_command` to use `find_url_by_short_code()` + `delete_url_from_database()` instead of inline SQL.

All print output stays identical. Only the database access method changes.

---

- [ ] **Step 3: Verify CLI still works**

```bash
del urls.db
python main.py shorten https://www.google.com/search?q=python
python main.py shorten https://github.com --alias github
python main.py resolve github
python main.py list
python main.py delete q0U
```

Every command must produce the same output as before. If anything fails, STOP and fix.

---

- [ ] **Step 4: Commit**

```bash
git add database.py main.py
git commit -m "extract shared database logic"
```

---

### Task 2: Create `app.py` with Core Flask Endpoints

**Files:**
- Create: `app.py`
- Create: `requirements.txt`

**Interfaces:**
- Consumes: All functions from `database.py` (Task 1)
- Produces: Flask web server with 4 endpoints:
  - `POST /shorten` — accepts JSON, returns JSON with short code (201)
  - `GET /<short_code>` — redirects to original URL (302), increments click count
  - `GET /stats/<short_code>` — returns JSON with click count, created_at, original URL (200)
  - `DELETE /<short_code>` — deletes the URL mapping (200)

---

- [ ] **Step 1: Create `requirements.txt`** — single line: `flask`

- [ ] **Step 2: Install Flask** — `pip install -r requirements.txt`

- [ ] **Step 3: Create `app.py`**

Structure:
- Import Flask + database functions
- `application = Flask(__name__)`
- `handle_shorten_request()` — validates JSON body, validates URL, handles alias vs auto-generated code, saves, returns JSON
- `handle_redirect_request(short_code)` — finds URL, increments click, returns `redirect(original_url, code=302)`
- `handle_stats_request(short_code)` — finds URL, returns JSON stats
- `handle_delete_request(short_code)` — finds URL, deletes, returns confirmation JSON
- `if __name__ == "__main__": setup_database(); application.run(debug=True, port=5000)`

Error responses:
- Missing/invalid JSON body → 400
- Invalid URL → 400
- Reserved alias name → 409
- Alias already taken → 409
- Short code not found → 404

---

- [ ] **Step 4: Verify all endpoints with curl**

Start server: `python app.py`

In separate terminal:
```bash
# Shorten
curl -X POST http://localhost:5000/shorten -H "Content-Type: application/json" -d "{\"url\": \"https://www.google.com\"}"

# Shorten with alias
curl -X POST http://localhost:5000/shorten -H "Content-Type: application/json" -d "{\"url\": \"https://github.com\", \"alias\": \"gh\"}"

# Invalid URL → 400
curl -X POST http://localhost:5000/shorten -H "Content-Type: application/json" -d "{\"url\": \"not-a-url\"}"

# Reserved alias → 409
curl -X POST http://localhost:5000/shorten -H "Content-Type: application/json" -d "{\"url\": \"https://example.com\", \"alias\": \"analytics\"}"

# Redirect → 302
curl -v http://localhost:5000/gh

# Stats → 200 with click_count: 1
curl http://localhost:5000/stats/gh

# Delete → 200
curl -X DELETE http://localhost:5000/gh

# Delete nonexistent → 404
curl -X DELETE http://localhost:5000/doesnotexist

# CLI still works
python main.py list
```

---

- [ ] **Step 5: Code simplicity review** — check naming, zero comments, no 30+ line functions, nothing AI-looking

- [ ] **Step 6: Commit**

```bash
git add app.py requirements.txt
git commit -m "add flask web api with core endpoints"
```

---

# Phase 2: TTL Expiry + API Key Auth

**What this accomplishes:** URLs can optionally expire after N seconds. Expired links return `410 Gone` and get deleted from the database on access. DELETE endpoint requires an API key.

---

### Task 3: Add TTL Expiry Support

**Files:**
- Modify: `database.py` (add `check_if_url_is_expired` function)
- Modify: `app.py` (update 3 route handlers + imports)

**Interfaces:**
- Produces: `check_if_url_is_expired(url_row)` — returns `True` if `expires_at` is set and in the past

---

- [ ] **Step 1: Add `check_if_url_is_expired` to `database.py`**

```python
def check_if_url_is_expired(url_row):
    expiry_timestamp = url_row["expires_at"]

    if expiry_timestamp is None:
        return False

    expiry_datetime = datetime.strptime(expiry_timestamp, "%Y-%m-%d %H:%M:%S")
    current_datetime = datetime.now()

    return current_datetime > expiry_datetime
```

---

- [ ] **Step 2: Update `app.py` imports** — add `check_if_url_is_expired`

- [ ] **Step 3: Update `handle_shorten_request`** — read `ttl_seconds` from request body, pass to `save_url_to_database(..., ttl_seconds=ttl_seconds)`, include in response if set

- [ ] **Step 4: Update `handle_redirect_request`** — after finding URL row, before incrementing clicks: check `check_if_url_is_expired(url_row)`. If expired: delete row, commit, return 410.

- [ ] **Step 5: Update `handle_stats_request`** — same expiry check pattern as redirect

- [ ] **Step 6: Verify TTL**

```bash
# Shorten with 5-second TTL
curl -X POST http://localhost:5000/shorten -H "Content-Type: application/json" -d "{\"url\": \"https://example.com\", \"ttl_seconds\": 5}"

# Immediately check stats → 200
curl http://localhost:5000/stats/<code>

# Wait 6 seconds, try redirect → 410 "This link has expired"
curl -v http://localhost:5000/<code>

# Try stats again → 404 (row was deleted on expired access)
curl http://localhost:5000/stats/<code>

# Shorten WITHOUT TTL → verify it never expires
```

- [ ] **Step 7: Commit** — `git commit -m "add link expiry with ttl"`

---

### Task 4: Add API Key Authentication for DELETE

**Files:**
- Modify: `app.py`

---

- [ ] **Step 1: Add `import os` to `app.py`**

- [ ] **Step 2: Add auth check at top of `handle_delete_request`**

```python
expected_api_key = os.environ.get("API_KEY")
provided_api_key = request.headers.get("X-API-Key")

if expected_api_key is not None and provided_api_key != expected_api_key:
    return jsonify({"error": "Invalid or missing API key"}), 401
```

If `API_KEY` env var isn't set, DELETE works without auth. Gets replaced by per-user auth in Phase 3.

- [ ] **Step 3: Verify**

```bash
set API_KEY=mysecretkey123
python app.py

# No key → 401
curl -X DELETE http://localhost:5000/<code>

# Wrong key → 401
curl -X DELETE http://localhost:5000/<code> -H "X-API-Key: wrongkey"

# Correct key → 200
curl -X DELETE http://localhost:5000/<code> -H "X-API-Key: mysecretkey123"
```

- [ ] **Step 4: Phase 2 full checkpoint** — shorten, redirect, stats, TTL expiry, auth delete, CLI `list`. Fix anything broken.

- [ ] **Step 5: Commit** — `git commit -m "add api key auth for delete"`

---

**Continue to Phase 3-4 plan:** `docs/superpowers/plans/2026-09-29-flask-web-api-phase3-4.md`
