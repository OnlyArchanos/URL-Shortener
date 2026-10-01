# URL Shortener (Couldn't decide on a good name so i just decided to name it this)

A Python URL shortener with both a CLI and a web API.
Started as a simple CLI project, then i got carried away and added a whole Flask web server on top of it ✌️ Still no external packages beyond Flask, no third-party API keys, just Python and SQL.
I tried to follow the same architecture that [Bitly uses in production](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly), and kinda adapted it for a local setup.

theres a live version running at **https://url-shortener-5ph2.onrender.com/** if you wanna try it without cloning anything. might take a few seconds to wake up on first load (free tier things).

## Running It

You need Python 3.6+.

```bash
git clone https://github.com/YOUR_USERNAME/url-shortener.git
cd url-shortener
pip install -r requirements.txt
```

The database (`urls.db`) gets created automatically on first run.

### CLI

```bash
python main.py
```

### Web Server

```bash
python app.py
```

Runs on `http://localhost:5000` by default.

## CLI Usage

all the original commands still work, nothing changed here:

**Shorten a URL:**

```
python main.py shorten https://www.google.com/search?q=python
```

```
URL shortened successfully!
  Original   : https://www.google.com/search?q=python
  Short Code : q0U
```

**Pick your own alias:**

```
python main.py shorten https://github.com --alias github
```

**Get the original URL back:**

```
python main.py resolve github
```

**See everything:**

```
python main.py list
```

**Delete one:**

```
python main.py delete q0U
```

## Web API

the web server adds user accounts, link expiry, rate limiting, and an analytics page. this is where it gets fun:

### Register

```bash
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret123"}'
```

```json
{"message": "User 'alice' created successfully", "api_key": "abc123..."}
```

save that `api_key`, you need it for everything else. lose it and you gotta login again.

### Login

```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret123"}'
```

returns your api key if you forgot it.

### Shorten a URL

```bash
curl -X POST http://localhost:5000/shorten \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"url": "https://www.google.com"}'
```

```json
{"short_code": "q0U", "short_url": "http://localhost:5000/q0U", "original_url": "https://www.google.com"}
```

you can also pass `"alias": "whatever"` for a custom short code, and `"ttl_seconds": 300` to make it expire after 5 minutes. pretty nifty.

### Redirect

just visit `http://localhost:5000/q0U` in your browser (or curl it). it redirects to the original URL. this is the only endpoint that doesnt need auth.

### Stats

```bash
curl http://localhost:5000/stats/q0U -H "X-API-Key: YOUR_API_KEY"
```

```json
{"short_code": "q0U", "original_url": "https://www.google.com", "click_count": 3, "created_at": "2026-09-29 18:30:00", "is_custom": false}
```

you can only see stats for your own URLs.

### Delete

```bash
curl -X DELETE http://localhost:5000/q0U -H "X-API-Key: YOUR_API_KEY"
```

you can only delete your own URLs.

### Analytics

```bash
curl http://localhost:5000/analytics -H "X-API-Key: YOUR_API_KEY"
```

returns an HTML page with a table of your top 5 URLs sorted by click count. nothing fancy, just a clean table.

> **windows users:** if you're using PowerShell, `curl` is actually an alias for `Invoke-RestMethod` and the syntax is different. use this instead:
> ```powershell
> Invoke-RestMethod -Uri http://localhost:5000/register -Method POST -ContentType "application/json" -Body '{"username":"alice","password":"secret123"}'
> ```
> save the api key in a variable with `$key = "YOUR_KEY"` then pass it like:
> ```powershell
> Invoke-RestMethod -Uri http://localhost:5000/shorten -Method POST -ContentType "application/json" -Headers @{"X-API-Key"=$key} -Body '{"url":"https://google.com"}'
> ```

## Error Codes

| Code | What it means |
|------|--------------|
| 400 | bad request (missing fields, invalid URL) |
| 401 | missing or wrong API key |
| 403 | trying to access someone else's URL |
| 404 | short code doesnt exist |
| 409 | alias already taken or reserved |
| 410 | link has expired |
| 429 | rate limited (max 10 shortens per minute) |

## How It Works

ok so the short version: theres a counter that starts at 100,000. every time you shorten a URL, i take that counter number and convert it to Base62 (digits + lowercase + uppercase = 62 characters). so 100,000 becomes `q0U`, 100,001 becomes `q0V`, and so on. no collisions ever because every number is unique. honestly this part is dead simple and thats the whole point.

the CLI (`main.py`) and the web server (`app.py`) both import from `database.py` which has all the shared logic — database setup, Base62 encoding, URL validation, user auth, everything. they share the same `urls.db` database so you can literally use both at the same time.

passwords are hashed with PBKDF2 (100k iterations, random salt) so even if someone gets the db file they cant just read your password. rate limiting uses a sliding window tracked in memory. link expiry checks happen on access — if a link is expired when someone tries to use it, it gets deleted right then and there 😭

theres more detail in [reference.md](reference.md) about how this maps to real production systems, and [explanation.md](explanation.md) walks through the CLI code line by line. [flask_explanation.md](flask_explanation.md) does the same for the web server.

## Project Structure

```
├── main.py               - CLI tool
├── app.py                - Flask web server
├── database.py           - shared database and auth logic
├── requirements.txt      - just flask
├── urls.db               - gets created on first run (gitignored)
├── reference.md          - system design notes
├── explanation.md        - line by line CLI walkthrough
├── flask_explanation.md  - line by line web server walkthrough
└── README.md
```
