# How This URL Shortener Actually Works

This is a reference file. If you want to understand the design decisions in this project or explain them in an interview, start here.

## The Two Operations

A URL shortener only does two things:

1. You give it a long URL, it gives you back a short code and remembers the pairing.
2. You give it a short code, it gives you back the original URL.

That's the whole product. Everything else is about making those two operations fast and reliable at scale.

## Generating Short Codes

There are really only two ways to do this.

**Hashing** — run the URL through something like MD5, grab the first 6 characters. Problem is, two different URLs can produce the same 6 characters. Now you need collision detection, retry logic, maybe appending random bits. It works, but it's more moving parts than necessary.

**Counter** — keep a number that starts at 100,000. Every new URL gets the current number converted to Base62, then the number goes up by one. No two URLs can ever get the same code because no two numbers are the same. This is what we use, and it's what Bitly uses in production.

## Base62 in 30 Seconds

You know how hex uses 16 characters (0-9, A-F) to represent numbers? Base62 uses 62: the digits 0-9, lowercase a-z, uppercase A-Z.

100,000 in Base62 is `q0U`. 100,001 is `q0V`. Six characters of Base62 can represent about 56.8 billion unique values, which is way more than we'll ever need.

We start the counter at 100,000 instead of 0 so that every code is at least 3 characters. Looks better.

## Where the Data Lives

SQLite. The database is a single file called `urls.db` that gets created next to `main.py` on first run.

There's a `urls` table with the mappings and a `counter` table that holds exactly one row (the current counter value). There's also an index on the `short_code` column so the database doesn't have to scan every row when you resolve a code.

Why SQLite and not Postgres? Because this is a CLI tool for one person. SQLite needs zero setup, ships with Python, and handles everything we need. A production system would use Postgres because it supports multiple connections, replication, network access, etc. But for this use case, SQLite is the right call.

## How This Maps to a Real System

Here's the thing that makes this project interesting for interviews: every piece of this CLI has a direct counterpart in how Bitly actually works.

| What we have | What Bitly has |
|---|---|
| `shorten` command | Write Service (separate microservice) |
| `resolve` command | Read Service (separate microservice) |
| `urls.db` file | PostgreSQL database |
| `counter` table | Redis instance storing the global counter |
| `idx_short_code` index | Database index (same concept, bigger scale) |
| Your terminal | Web/mobile client hitting an API |

The reason Bitly splits reads and writes into separate services is that reads happen way more often. Think about it: one person shortens a URL, then thousands of people click on it. So you want to be able to spin up more read servers without touching the write side.

## The Counter Problem at Scale

In our CLI, the counter lives in SQLite. One process, one counter, no issues.

But if Bitly has 10 write servers all creating URLs at the same time, they all need the next counter value without stepping on each other. Their solution: a single Redis instance that hands out counter values. Redis is fast (single-threaded, in-memory) and supports atomic increments, so two servers can't accidentally grab the same number.

To cut down on network calls, each server grabs a batch of values at once (like 1000) and uses them locally until they run out, then asks for another batch. Some numbers might get wasted if a server crashes mid-batch, but that's fine. You just need uniqueness, not continuity.

## The Caching Layer We Don't Have

A production URL shortener puts a cache (Redis, Memcached) between the read service and the database. When someone clicks a short link, the read service checks the cache first. If the URL is there, great, skip the database entirely. If not, look it up in the database and stuff it in the cache for next time.

We don't do this because a CLI doesn't need it. But our `resolve` command follows the same read path where you'd slot one in. The web server's `GET /<code>` redirect endpoint is the exact same read path — that's where a cache would go first.

## The Web API Layer

With `app.py`, we now have something that looks a lot closer to what Bitly actually runs. Instead of typing commands in a terminal, you send HTTP requests to endpoints. Here's how they map:

| What we have | What Bitly has |
|---|---|
| `POST /shorten` | Write Service API endpoint |
| `GET /<code>` (redirect) | Read Service / Redirect Service |
| `GET /stats/<code>` | Analytics API |
| `DELETE /<code>` | Admin API |
| `POST /register` + `POST /login` | Auth Service |
| `GET /analytics` | Dashboard UI |
| SQLite `urls.db` | PostgreSQL + Redis |
| In-memory rate limiter | Redis-backed rate limiter / API Gateway |

The interesting part is the read/write split. The redirect endpoint (`GET /<code>`) is public — no authentication needed. That's because in production, this is the hot path. Thousands of people click short links for every one person who creates one. You want this endpoint to be as fast and simple as possible.

Everything else (shortening, stats, delete) requires authentication. In production these would be behind an API gateway that handles auth, rate limiting, and routing. We do it in the application code because we don't need a separate gateway for a dev server.

## Multi-User Data Isolation

Every URL is tagged with a `user_id`. When alice shortens a URL, her user ID gets stored alongside it. When bob tries to see stats or delete that URL, we check if `url_row["user_id"] != authenticated_user["id"]` and return 403 if they don't match.

Redirects ignore this check on purpose — the whole point of a short URL is that anyone can click it.

In production you'd probably use database-level access controls (row-level security in Postgres) or a separate service that handles authorization. Our approach is simpler but follows the same principle: the data layer knows who owns what, and the API layer enforces access.

## Rate Limiting at Scale

Our rate limiter is an in-memory dictionary. Works fine for one server, but if you had 10 servers behind a load balancer, each one would have its own dictionary. Someone could send 10 requests to each server and effectively get 100 requests through.

The production fix: put the rate limit state in Redis. Redis supports atomic increments and key expiry, so you can implement the same sliding window pattern but shared across all servers. Some teams skip this entirely and use an API gateway (like Kong or AWS API Gateway) that handles rate limiting before requests even reach the application.

## Further Reading

The [Hello Interview writeup on Bitly](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly) covers all of this in more depth, including how to handle URL expiration, what HTTP status codes to use for redirects (302, not 301), and how to think about database sizing.

