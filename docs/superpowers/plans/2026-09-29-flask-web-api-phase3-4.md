# Flask Web API — Implementation Plan (Phases 3-4)

Continuation from `2026-09-29-flask-web-api-phase1-2.md`.

---

# Phase 3: Multi-User System

**What this accomplishes:** Multiple people can use the URL shortener. Each person registers with a username/password, gets a unique API key, and can only see/delete their own URLs. Short links (redirects) stay public.

---

### Task 5: Add User Authentication Functions to `database.py`

**Files:**
- Modify: `database.py` (add `hashlib`, `secrets` imports + 6 new functions)

**Interfaces:**
- Produces:
  - `hash_password(password_text)` — returns `"salt:hash"` string using PBKDF2-HMAC-SHA256, 100k iterations
  - `verify_password(password_text, stored_hash_string)` — returns `bool`
  - `generate_api_key()` — returns 64-char hex string via `secrets.token_hex(32)`
  - `create_new_user(database_connection, username, password_text)` — returns `(api_key, None)` or `(None, error_msg)`. Does NOT commit.
  - `authenticate_user_login(database_connection, username, password_text)` — returns `api_key` string or `None`
  - `find_user_by_api_key(database_connection, api_key_value)` — returns `sqlite3.Row` (with `id`, `username`, `created_at`) or `None`

---

- [ ] **Step 1: Add imports** — `import hashlib` and `import secrets` at top of `database.py`

- [ ] **Step 2: Add all 6 functions at bottom of `database.py`**

`hash_password`: generates random salt with `secrets.token_hex(16)`, hashes password with `hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, 100000)`, returns `"salt:hash_hex"`

`verify_password`: splits stored hash on `:`, re-derives key with same salt, compares hex digests

`generate_api_key`: returns `secrets.token_hex(32)`

`create_new_user`: checks if username exists (SELECT), if taken returns `(None, "Username is already taken.")`. Otherwise: hashes password, generates API key, inserts into users table, returns `(api_key, None)`.

`authenticate_user_login`: looks up user by username, verifies password. Returns api_key on success, None on failure.

`find_user_by_api_key`: SELECT from users WHERE api_key = ?, returns row or None.

---

- [ ] **Step 3: Verify with quick Python test**

```bash
python -c "from database import *; setup_database(); c = get_database_connection(); k, e = create_new_user(c, 'test', 'pass123'); c.commit(); print(k, e); print(authenticate_user_login(c, 'test', 'pass123')); print(authenticate_user_login(c, 'test', 'wrong')); c.close()"
```

Expected: API key printed, same key from login, `None` from wrong password.

- [ ] **Step 4: Commit** — `git commit -m "add user auth functions"`

---

### Task 6: Add Registration, Login, and User-Scoped Endpoints

**Files:**
- Modify: `app.py` (add 2 new routes, add auth helper, modify 3 existing routes)

**Interfaces:**
- Consumes: `create_new_user`, `authenticate_user_login`, `find_user_by_api_key` from Task 5
- Produces:
  - `POST /register` — creates user, returns API key (201)
  - `POST /login` — authenticates, returns API key (200)
  - `get_authenticated_user()` — helper returning `(user_row, None)` or `(None, error_response)`
  - Shorten, stats, delete now require auth + user ownership

---

- [ ] **Step 1: Update `app.py` imports** — add `create_new_user`, `authenticate_user_login`, `find_user_by_api_key`. Remove `import os` (env-var auth replaced).

- [ ] **Step 2: Add `get_authenticated_user()` helper**

```python
def get_authenticated_user():
    api_key_value = request.headers.get("X-API-Key")

    if api_key_value is None:
        return None, (jsonify({"error": "Missing X-API-Key header"}), 401)

    database_connection = get_database_connection()
    user_row = find_user_by_api_key(database_connection, api_key_value)
    database_connection.close()

    if user_row is None:
        return None, (jsonify({"error": "Invalid API key"}), 401)

    return user_row, None
```

Called at top of every auth-protected route. Returns `(user_row, None)` on success.

- [ ] **Step 3: Add `POST /register`**

Validates: JSON body, username (min 3 chars), password (min 6 chars). Calls `create_new_user()`. Returns 201 with api_key on success, 409 if username taken, 400 if validation fails.

- [ ] **Step 4: Add `POST /login`**

Validates: JSON body, username + password present. Calls `authenticate_user_login()`. Returns 200 with api_key, or 401 if credentials wrong.

- [ ] **Step 5: Update `handle_shorten_request`**

Add auth check at top: `authenticated_user, auth_error = get_authenticated_user()`. Pass `user_id=authenticated_user["id"]` to `save_url_to_database`.

- [ ] **Step 6: Update `handle_stats_request`**

Add auth check. After finding URL row, check `url_row["user_id"] != authenticated_user["id"]` → return 403 "You don't have access to this URL".

- [ ] **Step 7: Update `handle_delete_request`**

Replace env-var auth with `get_authenticated_user()`. Add user ownership check (403 if not owner).

- [ ] **Step 8: Verify multi-user system**

```bash
del urls.db
python app.py

# Register alice
curl -X POST http://localhost:5000/register -H "Content-Type: application/json" -d "{\"username\": \"alice\", \"password\": \"secret123\"}"
# Save ALICE_KEY from response

# Register bob
curl -X POST http://localhost:5000/register -H "Content-Type: application/json" -d "{\"username\": \"bob\", \"password\": \"password456\"}"
# Save BOB_KEY

# Duplicate registration → 409
curl -X POST http://localhost:5000/register -H "Content-Type: application/json" -d "{\"username\": \"alice\", \"password\": \"different\"}"

# Login → same key
curl -X POST http://localhost:5000/login -H "Content-Type: application/json" -d "{\"username\": \"alice\", \"password\": \"secret123\"}"

# Wrong password → 401
curl -X POST http://localhost:5000/login -H "Content-Type: application/json" -d "{\"username\": \"alice\", \"password\": \"wrong\"}"

# Alice shortens
curl -X POST http://localhost:5000/shorten -H "Content-Type: application/json" -H "X-API-Key: ALICE_KEY" -d "{\"url\": \"https://alice.com\"}"
# Save ALICE_CODE

# Bob can't see Alice's stats → 403
curl http://localhost:5000/stats/ALICE_CODE -H "X-API-Key: BOB_KEY"

# Bob can't delete Alice's URL → 403
curl -X DELETE http://localhost:5000/ALICE_CODE -H "X-API-Key: BOB_KEY"

# Alice CAN see her stats → 200
curl http://localhost:5000/stats/ALICE_CODE -H "X-API-Key: ALICE_KEY"

# Redirect still public (no auth needed) → 302
curl -v http://localhost:5000/ALICE_CODE

# CLI still works
python main.py list
```

- [ ] **Step 9: Commit** — `git commit -m "add user system with registration and login"`

---

# Phase 4: Rate Limiting + Analytics + Documentation

**What this accomplishes:** Abuse prevention, analytics visibility, and complete documentation.

---

### Task 7: Add Rate Limiting to POST /shorten

**Files:**
- Modify: `app.py`

**Interfaces:**
- Produces: `check_rate_limit(client_ip_address)` — returns `bool` (True = allowed)

---

- [ ] **Step 1: Add `import time` + rate limiter state**

After `application = Flask(__name__)`:
```python
request_timestamps_by_ip = {}
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60
```

- [ ] **Step 2: Add `check_rate_limit` function**

Sliding window approach: keeps list of timestamps per IP, prunes old ones, checks count vs limit.

```python
def check_rate_limit(client_ip_address):
    current_time = time.time()

    if client_ip_address not in request_timestamps_by_ip:
        request_timestamps_by_ip[client_ip_address] = []

    window_start_time = current_time - RATE_LIMIT_WINDOW_SECONDS
    recent_timestamps = [
        ts for ts in request_timestamps_by_ip[client_ip_address]
        if ts > window_start_time
    ]

    request_timestamps_by_ip[client_ip_address] = recent_timestamps

    if len(recent_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    recent_timestamps.append(current_time)
    return True
```

- [ ] **Step 3: Add rate limit check at top of `handle_shorten_request`** (before auth check)

```python
if not check_rate_limit(request.remote_addr):
    return jsonify({"error": "Rate limit exceeded. Try again in a minute."}), 429
```

- [ ] **Step 4: Verify** — temporarily set `RATE_LIMIT_MAX_REQUESTS = 3`, send 4 requests, 4th should return 429. Reset to 10.

- [ ] **Step 5: Commit** — `git commit -m "add rate limiting to shorten endpoint"`

---

### Task 8: Add Analytics Dashboard

**Files:**
- Modify: `database.py` (add `get_top_clicked_urls`)
- Modify: `app.py` (add `GET /analytics` route)

**Interfaces:**
- Produces: `get_top_clicked_urls(database_connection, user_id, result_limit)` — returns top N URLs by click count

---

- [ ] **Step 1: Add `get_top_clicked_urls` to `database.py`**

```python
def get_top_clicked_urls(database_connection, user_id, result_limit):
    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "SELECT short_code, original_url, click_count, created_at "
        "FROM urls WHERE user_id = ? ORDER BY click_count DESC LIMIT ?",
        (user_id, result_limit)
    )

    top_url_rows = database_cursor.fetchall()
    return top_url_rows
```

- [ ] **Step 2: Add imports to `app.py`** — add `get_top_clicked_urls` to database import block, add `import html` at top

- [ ] **Step 3: Add `GET /analytics` route**

Requires auth. Fetches top 5 URLs for the authenticated user. Builds a basic HTML table with minimal inline CSS. Uses `html.escape()` on all user-supplied data (URLs, short codes) for XSS safety.

The HTML: simple `<table>` with columns Short Code, Original URL, Clicks, Created. Sans-serif font, 800px max-width, basic border styling. No framework, no JavaScript.

If user has no URLs: shows "No URLs yet" in a colspan row.

- [ ] **Step 4: Verify** — create some URLs, click them a few times, check `/analytics` output via curl. Should return HTML with a sorted table.

- [ ] **Step 5: Commit** — `git commit -m "add analytics dashboard"`

---

### Task 9: Update Documentation

**Files:**
- Modify: `README.md`
- Create: `flask_explanation.md`
- Modify: `reference.md`
- Modify: `.agents/rules/project-rules.md`

---

- [ ] **Step 1: Update project rules** — change rule #8 to allow Flask as the single external dependency

- [ ] **Step 2: Rewrite `README.md`**

Cover both CLI and web API. Include:
- Setup: `pip install -r requirements.txt`
- Running CLI: `python main.py`
- Running web server: `python app.py`
- API docs: every endpoint with curl examples and sample responses
  - POST /register, POST /login
  - POST /shorten (with alias, with TTL)
  - GET /<code> (redirect)
  - GET /stats/<code>
  - DELETE /<code>
  - GET /analytics
- Error codes table

Same casual first-person voice as current README.

- [ ] **Step 3: Create `flask_explanation.md`**

Line-by-line walkthrough covering:
- What Flask is, what `Flask(__name__)` does
- How `@application.route()` decorators work
- `request.get_json()`, `jsonify()`, `redirect()`
- HTTP status codes (200, 201, 302, 400, 401, 403, 404, 409, 410, 429)
- The `get_authenticated_user()` pattern
- PBKDF2 password hashing explained simply
- Sliding window rate limiting explained
- How the analytics HTML is built

Conversational tone, same as `explanation.md`.

- [ ] **Step 4: Update `reference.md`**

Add web API architecture section:
- How Flask endpoints map to Bitly's API
- Read path (GET/<code> = public) vs write path (POST/shorten = auth required)
- Where caching would go in production
- Multi-user data isolation pattern

- [ ] **Step 5: Final verification checkpoint**

Full end-to-end:
1. CLI: shorten, resolve, list, delete — all work
2. Web: register, login, shorten, redirect, stats, delete — all work
3. TTL: expired links → 410 + deleted
4. Auth: wrong key → 401, wrong user → 403
5. Rate limiting: exceeding limit → 429
6. Analytics: HTML page with top 5
7. CLI and web server running simultaneously → both work

Code review: zero comments, descriptive names, no AI patterns, functions under 30 lines.

- [ ] **Step 6: Commit** — `git commit -m "update docs for flask web api"`

---

## Self-Review

**Spec coverage:** Every requirement maps to a task:
- POST /shorten → Task 2 | GET /<code> → Task 2 | GET /stats → Task 2 | DELETE → Task 2+4+6
- Collision handling → counter-based, collision-free
- Custom aliases → Task 1 (validate_custom_alias with reserved names)
- Expiry/TTL → Task 3 | Basic auth → Task 4+6 | Input validation → Task 1+2
- Analytics → Task 8 | Rate limiting → Task 7 | Multi-user → Tasks 5+6

**Placeholder scan:** No TBDs or TODOs.

**Type consistency:** `find_url_by_short_code` returns Row or None (Tasks 2,3,6). `save_url_to_database` signature consistent (Tasks 1,2,3,6). `get_authenticated_user` returns (row, None) or (None, response) (Tasks 6,7,8). `create_new_user` returns (key, None) or (None, msg) (Task 6).
