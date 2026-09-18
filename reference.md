# URL Shortener — System Design Reference

This document explains the system design concepts behind this URL shortener. It covers why each design decision was made and how this CLI relates to production URL shorteners like Bitly.

## The Core Problem

A URL shortener does two things:

1. **Write operation:** Take a long URL, produce a short unique code, store the mapping
2. **Read operation:** Take a short code, find the original URL, return it

In production systems like Bitly, reads happen far more often than writes. For every 1 URL shortened, the link might get clicked 1000 times. This "read-heavy" pattern influences every design decision.

## How Short Codes Are Generated

### Approach 1: Hash-Based (NOT used here)

Take the URL, run it through a hash function (like MD5 or SHA256), and use the first 6-8 characters as the short code.

**Problem:** Two different URLs could produce the same first 6 characters (a "collision"). You'd need extra logic to detect collisions, retry, or append random characters.

### Approach 2: Counter-Based with Base62 (USED here)

Keep a counter that starts at 100,000. Each time a URL is shortened:

1. Read the current counter value
2. Convert that number to Base62 (using characters `0-9`, `a-z`, `A-Z`)
3. Increment the counter
4. Use the Base62 string as the short code

**Why this is better:**
- **Zero collisions** — every counter value is unique
- **Predictable length** — starting at 100,000 gives 6+ character codes
- **Simple** — no collision handling needed
- **Production-proven** — Bitly uses this approach with a distributed counter (Redis)

### What is Base62?

Regular numbers use 10 digits (0-9). Hexadecimal uses 16 (0-9, A-F). Base62 uses 62: digits 0-9, lowercase a-z, uppercase A-Z. Large numbers become short strings.

| Decimal | Base62 |
|---------|--------|
| 100,000 | q0U |
| 100,001 | q0V |
| 1,000,000 | 4c92 |

With 6 characters, Base62 can represent 62^6 = **56.8 billion** unique codes.

## How This CLI Maps to Production Architecture

| Production Component | Purpose | CLI Equivalent |
|---|---|---|
| Client (web/mobile) | Sends requests | Your terminal |
| Write Service | Generates codes, saves to DB | `shorten` command |
| Read Service | Looks up codes, redirects | `resolve` command |
| Database (PostgreSQL) | Stores URL mappings | SQLite (`urls.db`) |
| Counter Service (Redis) | Tracks next counter value | `counter` table in SQLite |
| Database Index | Fast lookups by code | `idx_short_code` index |
| Cache (Redis) | Stores hot URLs in memory | Not needed at CLI scale |

## Why SQLite?

- **Zero config** — the database is just a file, no server to run
- **Built into Python** — `import sqlite3` works everywhere
- **Persistent** — data survives program restarts
- **Indexed** — supports indexes for fast lookups
- **ACID compliant** — data won't corrupt on crashes

In production, you'd use PostgreSQL for multi-user access, network support, and replication. For a single-user CLI, SQLite is the better choice.

## URL Validation

We check two things using Python's `urllib.parse`:

1. **Scheme** — must be `http` or `https`
2. **Domain** — must have a network location (like `google.com`)

## Error Handling Strategy

- Errors print to `stderr` (not `stdout`) so they don't mix with normal output
- Exit code `0` = success, `1` = error (Unix convention)
- Error messages explain what went wrong and what to do instead

## Scalability Patterns Used

1. **Counter-based codes** — scales via distributed counter (Redis) shared across servers
2. **Database indexes** — keeps lookups fast even with billions of rows
3. **Separated read/write** — `resolve` vs `shorten` mirrors production microservice split
4. **Data model** — same schema a production system would use

## Further Reading

- [Hello Interview: Design a URL Shortener Like Bitly](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly)
