# Code Walkthrough — main.py

Line-by-line breakdown of every function, variable, and decision in the codebase. If you're trying to understand what the code does or need to explain it to someone, this is the place.

---

## The Imports (Lines 1-7)

```python
import sqlite3
import os
import sys
import string
from datetime import datetime
from urllib.parse import urlparse
import argparse
```

Each one of these is from Python's standard library. No pip installs needed.

- `sqlite3` lets us talk to our SQLite database. SQLite is a lightweight database engine that stores everything in a single file. Python ships with it built in.
- `os` gives us filesystem operations. We use it to figure out where `main.py` is located so we can put the database file next to it.
- `sys` gives us access to `sys.stderr` (for printing errors separately from normal output) and `sys.exit()` (for quitting with an error code).
- `string` has pre-built character sets. We use `string.digits` (gives us `"0123456789"`), `string.ascii_lowercase` (gives us `"abcdef...z"`), and `string.ascii_uppercase` (gives us `"ABCDEF...Z"`). Saves us from typing all 62 characters by hand.
- `datetime` is specifically for getting the current time when we save a new URL. We import just the `datetime` class from the `datetime` module.
- `urlparse` is a function that breaks a URL into its pieces (scheme, domain, path, etc.). We use it to check if a URL is actually valid.
- `argparse` is Python's built-in library for building command-line interfaces. It handles parsing things like `python main.py shorten https://google.com --alias g` and gives us back structured data.

---

## The Constants (Lines 10-14)

```python
BASE62_CHARACTERS = string.digits + string.ascii_lowercase + string.ascii_uppercase

STARTING_COUNTER_VALUE = 100000

DATABASE_FILENAME = "urls.db"
```

**`BASE62_CHARACTERS`** ends up being the string `"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"`. That's 62 characters total. When we convert a counter number to a short code, we pick characters from this string. The character at index 0 is `"0"`, the character at index 61 is `"Z"`.

**`STARTING_COUNTER_VALUE`** is 100,000. We don't start at 0 or 1 because those would produce really short codes like `"0"` or `"1"`, which look weird as URL short codes. Starting at 100,000 means the first code is `"q0U"`, which is 3 characters. Looks more legit.

**`DATABASE_FILENAME`** is just the name of the SQLite file. It's defined once here so if you ever want to change it, you only change it in one place.

---

## get_database_path() — Lines 17-20

```python
def get_database_path():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    database_path = os.path.join(script_directory, DATABASE_FILENAME)
    return database_path
```

This figures out where to put the database file.

`__file__` is a special Python variable that holds the path to the current script. But it might be a relative path like `./main.py`, and we want an absolute one. `os.path.abspath(__file__)` converts it to something like `C:\Users\you\url-shortener\main.py`.

`os.path.dirname(...)` strips off the filename, leaving just the folder: `C:\Users\you\url-shortener\`.

`os.path.join(...)` tacks on `urls.db` to that folder path, giving us `C:\Users\you\url-shortener\urls.db`.

Why go through all this trouble? Because if you run `python C:\somewhere\else\main.py` from a different directory, `urls.db` still gets created next to `main.py`, not in whatever random folder you happened to be in.

---

## get_database_connection() — Lines 23-27

```python
def get_database_connection():
    database_path = get_database_path()
    database_connection = sqlite3.connect(database_path)
    database_connection.row_factory = sqlite3.Row
    return database_connection
```

Opens a connection to the SQLite database.

`sqlite3.connect(database_path)` opens the database file. If the file doesn't exist yet, SQLite creates it automatically.

The `row_factory = sqlite3.Row` line is worth explaining. By default, when you query SQLite in Python, you get back tuples like `(1, "q0U", "https://google.com", "2026-09-18")`. You'd have to remember that index 0 is the id, index 1 is the short code, etc. That's annoying and error-prone.

Setting `row_factory = sqlite3.Row` makes it so results come back as Row objects that you can access by column name. So instead of `row[1]` you write `row["short_code"]`. Way easier to read.

---

## setup_database() — Lines 30-65

```python
def setup_database():
    database_connection = get_database_connection()
    database_cursor = database_connection.cursor()
```

A cursor is how you send SQL commands to the database. Think of the connection as the phone line and the cursor as the person talking on it.

```python
    database_cursor.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_custom INTEGER NOT NULL DEFAULT 0
        )
    """)
```

This creates the `urls` table if it doesn't already exist. The columns:

- `id` — auto-incrementing number, mostly for internal use. `PRIMARY KEY` means each row gets a unique id. `AUTOINCREMENT` means SQLite handles assigning the numbers.
- `short_code` — the generated code or custom alias. `UNIQUE` means no two rows can have the same short code. `NOT NULL` means you can't leave it blank.
- `original_url` — the long URL the user wants to shorten.
- `created_at` — when the URL was shortened, stored as text like `"2026-09-18 18:30:00"`.
- `is_custom` — 0 if the code was auto-generated, 1 if the user picked their own alias. SQLite doesn't have a boolean type, so we use 0 and 1.

`CREATE TABLE IF NOT EXISTS` means this only runs if the table doesn't exist yet. So the first time you run the app it creates the table, and every time after that it's a no-op. Safe to call every time.

```python
    database_cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_short_code ON urls (short_code)
    """)
```

Creates an index on the `short_code` column. Without this, every time you resolve a code, SQLite would scan the entire table row by row looking for a match. With the index, it can jump straight to the right row. For 10 rows this doesn't matter. For 10 million rows it's the difference between instant and slow.

```python
    database_cursor.execute("""
        CREATE TABLE IF NOT EXISTS counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_value INTEGER NOT NULL
        )
    """)
```

The counter table. It stores one number: the next counter value to use for code generation.

`CHECK (id = 1)` is a constraint that means the `id` column can only ever be 1. This guarantees the table only ever has one row. It's a trick to make a "singleton" table, a table that stores a single value.

```python
    database_cursor.execute("SELECT COUNT(*) FROM counter")
    existing_row_count = database_cursor.fetchone()[0]

    if existing_row_count == 0:
        database_cursor.execute(
            "INSERT INTO counter (id, current_value) VALUES (1, ?)",
            (STARTING_COUNTER_VALUE,)
        )
```

Checks if the counter table is empty. If it is (first run), inserts the starting value of 100,000.

The `?` in the SQL is a parameter placeholder. The actual value (100,000) gets passed separately in the tuple `(STARTING_COUNTER_VALUE,)`. This is called a parameterized query. It prevents SQL injection attacks, which is when someone passes in malicious SQL through user input. The `?` makes sure the value is always treated as data, never as code.

That trailing comma in `(STARTING_COUNTER_VALUE,)` is important. Without it, Python treats the parentheses as just grouping, not as a tuple. `(100000)` is just the number 100000. `(100000,)` is a tuple containing 100000. SQLite expects a tuple.

```python
    database_connection.commit()
    database_connection.close()
```

`commit()` saves all the changes we made. Without it, everything would be rolled back when the connection closes. `close()` shuts down the connection and frees up resources.

---

## convert_number_to_base62() — Lines 68-82

```python
def convert_number_to_base62(decimal_number):
    if decimal_number == 0:
        return BASE62_CHARACTERS[0]
```

Edge case: if the number is 0, just return `"0"` (the first character in our alphabet). The loop below wouldn't execute at all for 0 because `0 > 0` is False.

```python
    base62_digits = []

    remaining_value = decimal_number
    while remaining_value > 0:
        remainder_index = remaining_value % 62
        base62_digits.append(BASE62_CHARACTERS[remainder_index])
        remaining_value = remaining_value // 62

    base62_digits.reverse()

    return "".join(base62_digits)
```

This is base conversion. Same idea as converting decimal to binary, but with 62 instead of 2.

Walk through it with 100,000:
- `100000 % 62 = 56` → `BASE62_CHARACTERS[56]` = `"U"`, then `100000 // 62 = 1612`
- `1612 % 62 = 0` → `BASE62_CHARACTERS[0]` = `"0"`, then `1612 // 62 = 26`
- `26 % 62 = 26` → `BASE62_CHARACTERS[26]` = `"q"`, then `26 // 62 = 0`
- Loop stops because `remaining_value` is now 0

`base62_digits` at this point is `["U", "0", "q"]`. We built the digits from least significant to most significant (right to left), so we reverse to get `["q", "0", "U"]`, then join into `"q0U"`.

`//` is integer division in Python. `100000 // 62` gives 1612, not 1612.9. We want whole numbers only.

---

## get_next_short_code() — Lines 85-100

```python
def get_next_short_code(database_connection):
    database_cursor = database_connection.cursor()

    database_cursor.execute("SELECT current_value FROM counter WHERE id = 1")
    counter_row = database_cursor.fetchone()
    current_counter_value = counter_row["current_value"]
```

Reads the current counter value from the database. `fetchone()` grabs the first (and only) row. Since we set up `row_factory` earlier, we can access the value by column name.

```python
    generated_short_code = convert_number_to_base62(current_counter_value)
```

Converts the counter to a Base62 string. First call gets 100000 → `"q0U"`, second call gets 100001 → `"q0V"`, etc.

```python
    next_counter_value = current_counter_value + 1
    database_cursor.execute(
        "UPDATE counter SET current_value = ? WHERE id = 1",
        (next_counter_value,)
    )

    return generated_short_code
```

Bumps the counter by 1 in the database. Notice we don't call `commit()` here. That's intentional. The caller (`handle_shorten_command`) will commit after the URL is also saved, so both the counter update and the URL insert are saved as one atomic operation. If the URL insert somehow fails, the counter doesn't get incremented either.

---

## check_if_url_is_valid() — Lines 103-109

```python
def check_if_url_is_valid(url_string):
    parsed_url_result = urlparse(url_string)

    has_valid_scheme = parsed_url_result.scheme in ("http", "https")
    has_domain_name = len(parsed_url_result.netloc) > 0

    return has_valid_scheme and has_domain_name
```

`urlparse` breaks a URL into parts. For `"https://www.google.com/search?q=hello"`:
- `scheme` = `"https"`
- `netloc` = `"www.google.com"`
- `path` = `"/search"`
- `query` = `"q=hello"`

We check two things: is the scheme http or https (not ftp, not mailto, not blank), and is there actually a domain name? If someone passes `"not-a-url"`, `urlparse` gives an empty scheme and empty netloc, so both checks fail.

The `in` keyword checks membership. `parsed_url_result.scheme in ("http", "https")` is True if the scheme is either "http" or "https".

---

## validate_custom_alias() — Lines 112-130

```python
def validate_custom_alias(alias_text, database_connection):
    if len(alias_text) == 0:
        return "Custom alias cannot be empty."

    if not alias_text.isalnum():
        return "Custom alias can only contain letters and numbers."
```

Two quick checks. `isalnum()` returns True if every character in the string is either a letter or a digit. So `"github"` passes, but `"my-link"` (has a hyphen) and `"my link"` (has a space) fail.

```python
    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "SELECT id FROM urls WHERE short_code = ?",
        (alias_text,)
    )
    existing_row = database_cursor.fetchone()

    if existing_row is not None:
        return f"The alias '{alias_text}' is already taken. Please choose a different one."

    return None
```

Checks the database to see if someone already used this alias. If `fetchone()` returns something (not None), the alias exists and we can't use it.

The function returns a string if there's a problem, or `None` if everything's fine. This is a pattern where `None` means "no error." The caller checks: if the return value isn't None, it's an error message, print it and bail out.

---

## save_url_to_database() — Lines 133-143

```python
def save_url_to_database(database_connection, short_code, original_url, is_custom_alias):
    database_cursor = database_connection.cursor()

    creation_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    custom_flag = 1 if is_custom_alias else 0

    database_cursor.execute(
        "INSERT INTO urls (short_code, original_url, created_at, is_custom) "
        "VALUES (?, ?, ?, ?)",
        (short_code, original_url, creation_timestamp, custom_flag)
    )
```

`datetime.now()` gets the current date and time. `.strftime("%Y-%m-%d %H:%M:%S")` formats it into a readable string like `"2026-09-18 18:30:00"`.

`1 if is_custom_alias else 0` is a one-line if/else (called a ternary expression). SQLite doesn't have booleans, so we store True as 1 and False as 0.

The INSERT uses four `?` placeholders, one for each value. The actual values go in the tuple at the end. Again, parameterized queries, never build SQL with f-strings.

Notice there's no `commit()` here either. Same reason as `get_next_short_code` — the caller handles committing so everything is saved together.

---

## handle_shorten_command() — Lines 146-181

This is the main "shorten" orchestrator. It ties together validation, code generation, and saving.

```python
def handle_shorten_command(url_to_shorten, custom_alias_text):
    if not check_if_url_is_valid(url_to_shorten):
        print(
            f"Error: '{url_to_shorten}' is not a valid URL. "
            "Make sure it starts with http:// or https://",
            file=sys.stderr
        )
        sys.exit(1)
```

First thing: check if the URL is valid. If not, print the error to `stderr` (not regular stdout) and exit with code 1. `file=sys.stderr` is a parameter of `print()` that redirects the output to the error stream. This matters if someone pipes the output of this command into another program — errors won't show up in the pipe, only in the terminal.

`sys.exit(1)` stops the program immediately with exit code 1. In Unix convention, exit code 0 means success and anything else means failure.

```python
    database_connection = get_database_connection()

    if custom_alias_text is not None:
        alias_error_message = validate_custom_alias(custom_alias_text, database_connection)

        if alias_error_message is not None:
            print(f"Error: {alias_error_message}", file=sys.stderr)
            database_connection.close()
            sys.exit(1)

        chosen_short_code = custom_alias_text
        is_custom = True
    else:
        chosen_short_code = get_next_short_code(database_connection)
        is_custom = False
```

Two branches: if the user gave us a custom alias (`--alias github`), validate it. If they didn't, generate one from the counter.

When `--alias` isn't used, argparse sets `custom_alias_text` to `None` (because we set `default=None` in the argument definition). So `None` means "no alias provided."

Note that if validation fails, we close the database connection before exiting. If we didn't, the connection would eventually get cleaned up by Python's garbage collector, but it's better practice to close it explicitly.

```python
    save_url_to_database(database_connection, chosen_short_code, url_to_shorten, is_custom)

    database_connection.commit()
    database_connection.close()
```

Save the URL, commit everything (the counter update and the URL insert happen together), close the connection.

```python
    print(f"\nURL shortened successfully!")
    print(f"  Original   : {url_to_shorten}")
    print(f"  Short Code : {chosen_short_code}")
    if is_custom:
        print(f"  (custom alias)")
    print()
```

Print the result. The `\n` at the start adds a blank line before the output so it doesn't butt up against the command prompt. `print()` with no arguments prints a blank line at the end for the same reason.

---

## handle_resolve_command() — Lines 184-209

```python
def handle_resolve_command(short_code_to_find):
    database_connection = get_database_connection()
    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "SELECT original_url, created_at, is_custom FROM urls WHERE short_code = ?",
        (short_code_to_find,)
    )
    found_row = database_cursor.fetchone()
    database_connection.close()
```

Looks up the short code in the database. `WHERE short_code = ?` filters to just the row with that code. `fetchone()` returns the first matching row, or `None` if there's no match.

We close the connection right after fetching because we're done with the database. We already have the data in `found_row`.

```python
    if found_row is None:
        print(
            f"Error: No URL found for short code '{short_code_to_find}'.",
            file=sys.stderr
        )
        sys.exit(1)

    url_type_label = "Custom Alias" if found_row["is_custom"] else "Auto-Generated"
```

If no row was found, tell the user and exit. Otherwise, figure out if it was a custom alias or auto-generated for the display label.

`found_row["is_custom"]` is either 0 or 1. In Python, 0 is falsy and 1 is truthy, so `if found_row["is_custom"]` works like a boolean check even though the actual value is an integer.

---

## URL_DISPLAY_MAX_LENGTH — Line 212

```python
URL_DISPLAY_MAX_LENGTH = 60
```

When listing all URLs, some might be really long (like 200 characters). If we print them as-is, the table gets unreadable. So we cap the display at 60 characters and add `...` to truncated ones.

---

## format_list_table_header() — Lines 215-233

```python
def format_list_table_header(code_column_width, url_column_width):
    date_column_width = 19
    type_column_width = 6
```

The date is always 19 characters (`"2026-09-18 18:30:00"`). The type is either `"Custom"` or `"Auto"`, max 6 characters. These are fixed. The code and URL columns vary based on the actual data, so their widths come in as parameters.

```python
    header_text = (
        f"  {'Short Code':<{code_column_width}}"
        f"  {'Original URL':<{url_column_width}}"
        f"  {'Created At':<{date_column_width}}"
        f"  {'Type':<{type_column_width}}"
    )
```

This is Python's f-string formatting. `{'Short Code':<{code_column_width}}` means: take the string `"Short Code"`, left-align it (`<`), and pad it with spaces until it's `code_column_width` characters wide. This is how the columns stay aligned.

The separator line uses `'-' * code_column_width` which creates a string of dashes as wide as the column. `'-' * 10` gives `"----------"`.

---

## format_list_table_row() — Lines 236-250

```python
def format_list_table_row(url_row, code_column_width, url_column_width):
    display_url = url_row["original_url"]
    if len(display_url) > URL_DISPLAY_MAX_LENGTH:
        display_url = display_url[:URL_DISPLAY_MAX_LENGTH - 3] + "..."
```

If the URL is longer than 60 characters, we chop it at character 57 and add `"..."` to make it exactly 60. `display_url[:57]` is Python slice syntax — it grabs the first 57 characters.

The rest of the function formats the row the same way as the header, using the same column widths so everything lines up.

---

## handle_list_command() — Lines 253-280

```python
    database_cursor.execute(
        "SELECT short_code, original_url, created_at, is_custom "
        "FROM urls ORDER BY created_at DESC"
    )
    all_url_rows = database_cursor.fetchall()
```

`fetchall()` grabs every row (not just one like `fetchone()`). `ORDER BY created_at DESC` sorts by creation date, newest first.

```python
    if len(all_url_rows) == 0:
        print("\nNo shortened URLs found. Use 'shorten' to create one.\n")
        return
```

If the table is empty, say so and bail out. The `return` here exits the function early — none of the table-printing code below runs.

```python
    longest_code = max(len(url_row["short_code"]) for url_row in all_url_rows)
    code_column_width = max(len("Short Code"), longest_code)
```

This calculates how wide the "Short Code" column needs to be. It finds the longest short code in the data, then picks whichever is bigger: that length or the header text `"Short Code"` (10 characters). So if all codes are 3 characters, the column is still 10 wide to fit the header.

The `max(len(...) for url_row in all_url_rows)` part is a generator expression. It loops through every row, gets the length of its short code, and `max()` picks the biggest one. It's the same as writing a for loop and tracking the maximum yourself, but in one line.

Same logic for the URL column, except we also cap it at `URL_DISPLAY_MAX_LENGTH` using `min()`.

---

## handle_delete_command() — Lines 283-314

Same pattern as resolve: look up the code, bail if it doesn't exist, but instead of printing the URL, we delete the row.

```python
    deleted_original_url = found_row["original_url"]
```

We save the URL before deleting the row, because after the DELETE the data is gone. We need it for the confirmation message.

```python
    database_cursor.execute(
        "DELETE FROM urls WHERE short_code = ?",
        (short_code_to_delete,)
    )

    database_connection.commit()
    database_connection.close()
```

`DELETE FROM urls WHERE short_code = ?` removes the matching row. We commit immediately because this is a destructive operation and we want it saved. Close the connection after.

---

## build_argument_parser() — Lines 317-364

This builds the entire command-line interface.

```python
    parser = argparse.ArgumentParser(
        prog="urlshort",
        description="A CLI-based URL shortener. ..."
    )
```

`ArgumentParser` is the top-level parser. `prog` is the name shown in help text.

```python
    subcommand_parsers = parser.add_subparsers(dest="command")
```

`add_subparsers` lets us define subcommands like `shorten`, `resolve`, etc. `dest="command"` means the chosen subcommand name gets stored in `parsed_args.command`. So if the user runs `python main.py shorten ...`, `parsed_args.command` will be the string `"shorten"`.

Each `add_parser(...)` call creates a subcommand, and `add_argument(...)` defines what arguments that subcommand accepts.

```python
    shorten_parser.add_argument(
        "--alias",
        default=None,
        help="Optional custom alias..."
    )
```

The `--` prefix makes this an optional argument. Without `--`, it would be a positional (required) argument. `default=None` means if the user doesn't provide `--alias`, `parsed_args.alias` will be `None`.

---

## main() — Lines 367-391

```python
def main():
    setup_database()

    argument_parser = build_argument_parser()
    parsed_args = argument_parser.parse_args()
```

Every time the program runs, we call `setup_database()` first. It creates the tables if they don't exist, and does nothing if they already do. Then we parse the command-line arguments.

```python
    if parsed_args.command is None:
        argument_parser.print_help()
        sys.exit(0)
```

If the user runs just `python main.py` without any subcommand, `parsed_args.command` is None. We show the help text and exit with code 0 (success, not an error — they just didn't give a command).

```python
    if parsed_args.command == "shorten":
        handle_shorten_command(parsed_args.url, parsed_args.alias)

    if parsed_args.command == "resolve":
        handle_resolve_command(parsed_args.code)

    if parsed_args.command == "list":
        handle_list_command()

    if parsed_args.command == "delete":
        handle_delete_command(parsed_args.code)
```

Simple routing. Check which command was used and call the right handler. Each handler is a separate function, which keeps `main()` short and readable.

```python
if __name__ == "__main__":
    main()
```

This is a Python convention. `__name__` is a special variable that Python sets to `"__main__"` when you run the file directly (like `python main.py`). If the file gets imported by another file (like `import main`), `__name__` would be `"main"` instead, and this block wouldn't execute.

It means: "only run `main()` if this file is being run directly, not if it's being imported as a module." For this project it doesn't matter much since we're always running it directly, but it's standard practice and a good habit.
