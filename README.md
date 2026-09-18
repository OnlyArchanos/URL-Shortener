# URL Shortener CLI

A command-line URL shortener built in Python. Takes long URLs and generates short, unique codes. Inspired by the system design behind [Bit.ly](https://bitly.com/).

Built with **only the Python standard library** — no external packages needed.

## How It Works

Every time you shorten a URL, the app:

1. Validates that your URL starts with `http://` or `https://` and has a proper domain
2. Generates a unique short code using **Base62 encoding** (characters: `0-9`, `a-z`, `A-Z`)
3. Stores the mapping in a local **SQLite database** (`urls.db`) so it persists across runs
4. Returns the short code to you

The short code generation uses a **counter-based approach** — the same strategy used by production URL shorteners like Bitly. A counter increments for each new URL, and the counter value is converted to Base62. This guarantees every code is unique with zero possibility of collisions.

## Requirements

- Python 3.6 or higher (no additional packages needed)

## Setup

Clone the repository and you're ready to go:

```bash
git clone https://github.com/YOUR_USERNAME/url-shortener.git
cd url-shortener
```

## Commands

### Shorten a URL

```bash
python main.py shorten <url>
```

**Example:**
```
$ python main.py shorten https://www.google.com/search?q=python+url+shortener

URL shortened successfully!
  Original   : https://www.google.com/search?q=python+url+shortener
  Short Code : q0U
```

### Shorten with a Custom Alias

```bash
python main.py shorten <url> --alias <your_alias>
```

**Example:**
```
$ python main.py shorten https://www.github.com --alias github

URL shortened successfully!
  Original   : https://www.github.com
  Short Code : github
  (custom alias)
```

### Resolve a Short Code

```bash
python main.py resolve <code>
```

**Example:**
```
$ python main.py resolve github

Resolved successfully!
  Short Code    : github
  Original URL  : https://www.github.com
  Created At    : 2026-09-18 18:30:00
  Type          : Custom Alias
```

### List All Shortened URLs

```bash
python main.py list
```

**Example:**
```
$ python main.py list

  Found 2 shortened URL(s):

  Short Code  Original URL                                          Created At           Type
  ----------  ------------                                          -------------------  ------
  github      https://www.github.com                                2026-09-18 18:30:00  Custom
  q0U         https://www.google.com/search?q=python+url+shortener  2026-09-18 18:29:00  Auto
```

### Delete a Shortened URL

```bash
python main.py delete <code>
```

**Example:**
```
$ python main.py delete q0U

Deleted successfully!
  Short Code    : q0U
  Original URL  : https://www.google.com/search?q=python+url+shortener
```

## Error Handling

| Scenario | What Happens |
|---|---|
| Invalid URL (no http/https) | Error message explaining the format needed |
| Custom alias already taken | Error message suggesting a different alias |
| Resolving a code that doesn't exist | Error message saying no URL was found |
| Deleting a code that doesn't exist | Error message saying no URL was found |
| Empty custom alias | Error message saying alias cannot be empty |
| Non-alphanumeric alias | Error message saying only letters and numbers allowed |

## Project Structure

```
url-shortener/
├── main.py          # All application logic
├── urls.db          # SQLite database (auto-created on first run)
├── README.md        # This file
└── reference.md     # System design concepts explained
```

## Design Decisions

See [reference.md](reference.md) for a detailed explanation of the system design concepts behind this project, including why counter-based encoding was chosen over hashing, and how this CLI maps to a production URL shortener architecture.
