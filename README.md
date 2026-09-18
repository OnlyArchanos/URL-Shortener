# URL Shortener CLI

A Python CLI tool that shortens URLs. No external packages, no API keys, just Python and SQLite.

## Running It

You need Python 3.6+. That's it.

```bash
git clone https://github.com/YOUR_USERNAME/url-shortener.git
cd url-shortener
python main.py
```

The database (`urls.db`) gets created automatically on first run.

## Usage

**Shorten a URL:**
```
python main.py shorten https://www.google.com/search?q=python
```
```
URL shortened successfully!
  Original   : https://www.google.com/search?q=python
  Short Code : q0U
```

**Use a custom alias instead:**
```
python main.py shorten https://github.com --alias github
```
```
URL shortened successfully!
  Original   : https://github.com
  Short Code : github
  (custom alias)
```

**Get the original URL back:**
```
python main.py resolve github
```
```
Resolved successfully!
  Short Code    : github
  Original URL  : https://github.com
  Created At    : 2026-09-18 18:30:00
  Type          : Custom Alias
```

**See everything you've shortened:**
```
python main.py list
```
```
  Found 2 shortened URL(s):

  Short Code  Original URL                                  Created At           Type
  ----------  ------------                                  -------------------  ------
  github      https://github.com                            2026-09-18 18:30:00  Custom
  q0U         https://www.google.com/search?q=python        2026-09-18 18:29:00  Auto
```

**Remove one:**
```
python main.py delete q0U
```
```
Deleted successfully!
  Short Code    : q0U
  Original URL  : https://www.google.com/search?q=python
```

If you pass a bad URL, a taken alias, or a code that doesn't exist, you'll get a clear error message telling you what went wrong.

## What's Going On Under the Hood

Each URL gets a short code by converting an incrementing counter into Base62 (digits + lowercase + uppercase = 62 characters). The counter starts at 100,000 so codes are always at least 6 characters. Every mapping lives in a SQLite database, so nothing disappears when you close the terminal.

No hashing, no collision handling, no retries. Counter goes up, you get a unique code. Simple.

## Why This Design Scales

This project follows the same architecture that [Bitly uses in production](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly), adapted for a local CLI.

The `shorten` command is basically a write service. The `resolve` command is a read service. In a real system, you'd run these as separate microservices because reads outnumber writes by ~1000:1, and you want to scale them independently.

The counter lives in its own table. In production, this would be a Redis instance that multiple servers share. Each server grabs a batch of counter values (say 1000 at a time) so they don't need to call Redis on every single request. We don't need that here, but the pattern is the same.

There's an index on the `short_code` column. Without it, every resolve would scan the entire table looking for a match. With it, the database jumps straight to the right row. This is what makes lookups fast even with millions of entries.

A real system would also have a caching layer (Redis or Memcached) sitting in front of the database for hot URLs. We skip that because a CLI doesn't need it, but the read path is structured the same way you'd add one.

For a deeper breakdown of how all this works at scale, check out the [Hello Interview writeup on Bitly](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly). The [reference.md](reference.md) file in this repo also maps each production component to its CLI equivalent.

## Project Structure

```
├── main.py        - all the code
├── urls.db        - created on first run, gitignored
├── reference.md   - system design notes
└── README.md
```
