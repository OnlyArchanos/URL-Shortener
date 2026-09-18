# URL Shortener CLI (Couldn't decide on a good name so i just decided to name it this)

A Python CLI tool that shortens URLs.
This is a simple project, i have used no external packages, no API keys, just Python and SQL.
I have tried to follow the same architecture that [Bitly uses in production](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly), and kind of changed it for a local CLI.

## Running It

You need Python 3.6+. (havent tested it for other versions yet but it should work)

```bash
git clone https://github.com/YOUR_USERNAME/url-shortener.git
cd url-shortener
python main.py
```

The database (`urls.db`) gets created automatically on first run.

## Usage (Tried to make the workflow pretty simple here)

**Shorten a URL:**

```
python main.py shorten https://www.google.com/search?q=python
```

```
URL shortened successfully!
  Original   : https://www.google.com/search?q=python
  Short Code : q0U
```

**You can also pick your own alias if you want:**

```
python main.py shorten https://github.com --alias github
```

```
URL shortened successfully!
  Original   : https://github.com
  Short Code : github
  (custom alias)
```

**Get the original URL back from a code:**

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

**See everything you've shortened so far:**

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

**Delete one you dont need anymore:**

```
python main.py delete q0U
```

```
Deleted successfully!
  Short Code    : q0U
  Original URL  : https://www.google.com/search?q=python
```

i tried to handle most error cases, so if you pass a bad URL or try to use an alias thats already taken or look up a code that doesnt exist, it should tell you whats wrong instead of just crashing.

## How it works (keeping it short)

So basically every URL gets a short code by converting a counter number into Base62. Base62 just means i use digits + lowercase + uppercase letters as the "alphabet" (62 characters total). The counter starts at 100,000 so the codes always come out to at least a few characters long.

Everything gets saved in a SQLite database file so your URLs dont disappear when you close the terminal. i went with SQLite because it doesnt need any setup, its just a file, and Python has it built in.

i didnt use hashing for the short codes because that would mean dealing with collisions (two URLs getting the same code). With a counter thats impossible since each number only gets used once.

## How this relates to real URL shorteners

i read through [this Bitly system design breakdown](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly) and tried to follow the same patterns here, just scaled down for a CLI.

The way i see it, my `shorten` command is doing what a write service would do in production, and `resolve` is the read service. In a real system these would be separate microservices because way more people click short links than create them (like 1000:1 ratio apparently), so you want to scale reads separately from writes.

The counter in my code lives in a SQLite table. In production it would be a Redis instance. Multiple servers would share that one Redis counter, and each server grabs a batch of numbers at once (like 1000 at a time) so they dont have to keep going back to Redis for every single URL. i dont need batching here obviously, but the idea is the same.

i also added an index on the `short_code` column in the database. Without it, looking up a code would mean scanning every single row which gets slow fast. With the index, the database can jump right to the matching row. This is basically the same thing production databases do.

A real system would also have a cache (like Redis or Memcached) sitting between the read service and the database to avoid hitting the database for popular links. i skipped that since a CLI doesnt need it, but the code is structured in a way where you could add one.

If you want to read more about all of this, the [Hello Interview writeup](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly) goes into way more detail. i also wrote a [reference.md](reference.md) file that maps each production component to what i used in this project.

## Project Structure

```
├── main.py           - all the code lives here
├── urls.db           - gets created when you first run it (gitignored)
├── reference.md      - system design notes and how this maps to production
├── explanation.md    - line by line code walkthrough if you want to understand the code
└── README.md
```

