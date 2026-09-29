# Flask Web Server — How Everything Works

this is a walkthrough of `app.py` and the web-related parts of `database.py`. if you havent read [explanation.md](explanation.md) yet, start there — it covers the CLI code and the shared database stuff that the web server builds on top of.

## what even is Flask

Flask is a Python library for building web servers. when you run `python app.py`, it starts a little server on your computer that listens for HTTP requests (like when your browser visits a URL or when you use `curl`). you write Python functions that handle those requests and return responses.

the whole thing starts with this:

```python
application = Flask(__name__)
```

thats it. thats your web server. `__name__` just tells Flask what module its running in (Python uses this internally). from here you add "routes" which are just URLs that map to functions.

## routes and decorators

every endpoint looks like this:

```python
@application.route("/shorten", methods=["POST"])
def handle_shorten_request():
    ...
```

the `@application.route(...)` line is a decorator. it tells Flask "when someone sends a POST request to `/shorten`, run this function." the function reads the request, does stuff, and returns a response.

Flask gives you a few key tools:
- `request.get_json()` — grabs the JSON body from the request
- `jsonify({"key": "value"})` — turns a Python dict into a JSON response
- `redirect(url, code=302)` — sends the browser to a different URL
- `request.headers.get("X-API-Key")` — reads a specific header

## the authentication pattern

most endpoints need you to prove who you are. thats what the `get_authenticated_user()` function does:

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

it returns a tuple: `(user, error)`. if the user is authenticated, you get `(user_row, None)`. if not, you get `(None, error_response)`. every protected endpoint starts with:

```python
authenticated_user, auth_error = get_authenticated_user()
if auth_error is not None:
    return auth_error
```

this pattern is nice because it keeps the auth check to two lines per endpoint. no decorators, no middleware, just a function call.

## registration and login

when you register, your password gets hashed before its stored. we never store the actual password.

the hashing uses PBKDF2 which stands for Password-Based Key Derivation Function 2. dont worry about the name, heres what it does:

1. generate a random "salt" (a random string, different for every user)
2. combine the password + salt and hash it 100,000 times
3. store the salt and final hash together as `"salt:hash"`

when you login, we split the stored string back into the salt and hash, re-hash your password with the same salt, and check if the results match. the 100,000 iterations make brute-force attacks really slow — even if someone gets the database, they cant just reverse the hash.

the API key is generated with `secrets.token_hex(32)` which gives you 64 random hex characters. its basically a random password that you send with every request instead of your username/password.

## how the endpoints work

**POST /shorten** — validates the URL, checks if you passed a custom alias (and if its valid/available), generates a short code if you didnt, saves everything to the database with your user ID attached. if you included `ttl_seconds`, it calculates an expiry timestamp.

**GET /<short_code>** — this is the redirect. its the only public endpoint (no auth needed). looks up the code, checks if its expired (if so, deletes it and returns 410 Gone), increments the click count, and sends a 302 redirect to the original URL.

**GET /stats/<short_code>** — requires auth. finds the URL, checks if YOU own it (returns 403 if not), checks expiry, returns the stats as JSON.

**DELETE /<short_code>** — requires auth. same ownership check. deletes the row.

**GET /analytics** — requires auth. queries your top 5 URLs by click count and builds a simple HTML table. uses `html.escape()` on all user data to prevent XSS (cross-site scripting — where someone puts JavaScript in a URL and it runs when you view the page).

## HTTP status codes

these are the numbers that come back with every response. heres what each one means:

- **200** — everything worked
- **201** — something was created (new URL, new user)
- **302** — redirect (your browser follows this automatically)
- **400** — you sent bad data (missing fields, invalid URL)
- **401** — not authenticated (missing or wrong API key)
- **403** — authenticated but not authorized (trying to see someone elses stuff)
- **404** — that short code doesnt exist
- **409** — conflict (alias already taken, username taken)
- **410** — gone (the link expired)
- **429** — too many requests (rate limited)

## rate limiting

the rate limiter uses a "sliding window" approach. heres how it works:

theres a dictionary called `request_timestamps_by_ip` that maps each IP address to a list of timestamps. every time someone tries to shorten a URL:

1. look at their list of timestamps
2. throw away anything older than 60 seconds
3. if theres 10 or more timestamps left, reject with 429
4. otherwise, add the current time and let them through

its stored in memory (a regular Python dict), so it resets when you restart the server. a production system would use Redis for this, but for a dev server its fine.

the limit is 10 requests per minute, only on the `/shorten` endpoint. redirects arent rate limited because you want those to be fast and unrestricted.

## TTL (time to live)

when you shorten a URL with `ttl_seconds`, we calculate an expiry timestamp:

```python
expiry_datetime = datetime.now() + timedelta(seconds=int(ttl_seconds))
```

this gets stored in the `expires_at` column. when someone tries to access the URL (redirect or stats), we check:

```python
def check_if_url_is_expired(url_row):
    if url_row["expires_at"] is None:
        return False
    expiry_datetime = datetime.strptime(url_row["expires_at"], "%Y-%m-%d %H:%M:%S")
    return datetime.now() > expiry_datetime
```

if its expired, we delete the row right then and there and return 410 Gone. this is called "lazy deletion" — we dont have a background job scanning for expired links, we just clean them up when someone tries to use them.

## the analytics page

the `/analytics` endpoint is the only one that returns HTML instead of JSON. its a simple table built with string concatenation — no template engine, no JavaScript, just raw HTML with inline CSS.

the important thing is `html.escape()`. any time we put user data into HTML (short codes, URLs), we escape it first. without this, someone could create a URL like `<script>alert('hacked')</script>` and it would actually run as JavaScript when you view the analytics page. `html.escape()` turns `<` into `&lt;` and `>` into `&gt;` so it just shows up as text.
