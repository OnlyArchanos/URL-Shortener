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

i tried to handle most of the error cases i could think of, like if you pass some random string thats not a URL, or try to use an alias someones already taken, or look up a code that doesnt exist. it wont just crash on you, itll tell you what went wrong.

## how it works

ok so the short version: theres a counter that starts at 100,000. every time you shorten a URL, i take that counter number and convert it to something called Base62. thats just a fancy way of saying i turn the number into a mix of digits, lowercase letters, and uppercase letters (62 characters total, hence the name). so 100,000 becomes `q0U`, 100,001 becomes `q0V`, and so on.

then the counter goes up by 1 and we do it again next time. thats it. no hashing, no worrying about two URLs accidentally getting the same code. every number is unique so every code is unique.

everything gets stored in a SQLite database which is literally just a file called `urls.db`. i picked SQLite because theres nothing to install or set up, Python already has it built in, and it just works.

## how this relates to actual production systems

so i found [this system design breakdown of how Bitly works](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly) and basically tried to copy the same patterns, just way smaller.

like my `shorten` command? thats basically what Bitly's write service does. and `resolve` is their read service. in production those would be completely separate servers because apparently for every 1 person who shortens a URL, like 1000 people end up clicking it. so you need way more read servers than write servers.

the counter thing is pretty similar too. Bitly uses Redis for their counter (its fast, sits in memory). when they have like 10 servers all shortening URLs at the same time, each server grabs a batch of counter numbers (like 1000 at once) so they dont all fight over the same Redis instance. i obviously dont need to do that for a CLI tool lol but the concept is there.

oh and i added a database index on the `short_code` column. without that, every time you resolve a code itd have to look through every single row in the table. with the index it just jumps straight to the right one. same thing real databases do when they have millions of rows.

a real URL shortener would also have a caching layer so popular links dont hit the database every single time someone clicks them. didnt add that here cause... its a CLI. but if you look at how `resolve` works you can kinda see where youd slot one in.

theres more detail about all this in the [Hello Interview writeup](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly) if youre curious. i also put together a [reference.md](reference.md) that maps out what each part of my code corresponds to in a real production system.

## project structure

```
├── main.py           - all the code lives here
├── urls.db           - gets created when you first run it (gitignored)
├── reference.md      - system design notes
├── explanation.md    - line by line code walkthrough if youre into that
└── README.md
```
