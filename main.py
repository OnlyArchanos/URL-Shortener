import sqlite3
import os
import sys
import string
from datetime import datetime
from urllib.parse import urlparse
import argparse


BASE62_CHARACTERS = string.digits + string.ascii_lowercase + string.ascii_uppercase

STARTING_COUNTER_VALUE = 100000

DATABASE_FILENAME = "urls.db"


def get_database_path():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    database_path = os.path.join(script_directory, DATABASE_FILENAME)
    return database_path


def get_database_connection():
    database_path = get_database_path()
    database_connection = sqlite3.connect(database_path)
    database_connection.row_factory = sqlite3.Row
    return database_connection


def setup_database():
    database_connection = get_database_connection()
    database_cursor = database_connection.cursor()

    database_cursor.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_custom INTEGER NOT NULL DEFAULT 0
        )
    """)

    database_cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_short_code ON urls (short_code)
    """)

    database_cursor.execute("""
        CREATE TABLE IF NOT EXISTS counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_value INTEGER NOT NULL
        )
    """)

    database_cursor.execute("SELECT COUNT(*) FROM counter")
    existing_row_count = database_cursor.fetchone()[0]

    if existing_row_count == 0:
        database_cursor.execute(
            "INSERT INTO counter (id, current_value) VALUES (1, ?)",
            (STARTING_COUNTER_VALUE,)
        )

    database_connection.commit()
    database_connection.close()


def convert_number_to_base62(decimal_number):
    if decimal_number == 0:
        return BASE62_CHARACTERS[0]

    base62_digits = []

    remaining_value = decimal_number
    while remaining_value > 0:
        remainder_index = remaining_value % 62
        base62_digits.append(BASE62_CHARACTERS[remainder_index])
        remaining_value = remaining_value // 62

    base62_digits.reverse()

    return "".join(base62_digits)


def get_next_short_code(database_connection):
    database_cursor = database_connection.cursor()

    database_cursor.execute("SELECT current_value FROM counter WHERE id = 1")
    counter_row = database_cursor.fetchone()
    current_counter_value = counter_row["current_value"]

    generated_short_code = convert_number_to_base62(current_counter_value)

    next_counter_value = current_counter_value + 1
    database_cursor.execute(
        "UPDATE counter SET current_value = ? WHERE id = 1",
        (next_counter_value,)
    )

    return generated_short_code


def check_if_url_is_valid(url_string):
    parsed_url_result = urlparse(url_string)

    has_valid_scheme = parsed_url_result.scheme in ("http", "https")
    has_domain_name = len(parsed_url_result.netloc) > 0

    return has_valid_scheme and has_domain_name


def validate_custom_alias(alias_text, database_connection):
    if len(alias_text) == 0:
        return "Custom alias cannot be empty."

    if not alias_text.isalnum():
        return "Custom alias can only contain letters and numbers."

    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "SELECT id FROM urls WHERE short_code = ?",
        (alias_text,)
    )
    existing_row = database_cursor.fetchone()

    if existing_row is not None:
        return f"The alias '{alias_text}' is already taken. Please choose a different one."

    return None


def save_url_to_database(database_connection, short_code, original_url, is_custom_alias):
    database_cursor = database_connection.cursor()

    creation_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    custom_flag = 1 if is_custom_alias else 0

    database_cursor.execute(
        "INSERT INTO urls (short_code, original_url, created_at, is_custom) "
        "VALUES (?, ?, ?, ?)",
        (short_code, original_url, creation_timestamp, custom_flag)
    )


def handle_shorten_command(url_to_shorten, custom_alias_text):
    if not check_if_url_is_valid(url_to_shorten):
        print(
            f"Error: '{url_to_shorten}' is not a valid URL. "
            "Make sure it starts with http:// or https://",
            file=sys.stderr
        )
        sys.exit(1)

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

    save_url_to_database(database_connection, chosen_short_code, url_to_shorten, is_custom)

    database_connection.commit()
    database_connection.close()

    print(f"\nURL shortened successfully!")
    print(f"  Original   : {url_to_shorten}")
    print(f"  Short Code : {chosen_short_code}")
    if is_custom:
        print(f"  (custom alias)")
    print()


def build_argument_parser():
    parser = argparse.ArgumentParser(
        prog="urlshort",
        description="A CLI-based URL shortener. "
                     "Shorten long URLs, resolve short codes, "
                     "and manage your shortened links."
    )

    subcommand_parsers = parser.add_subparsers(dest="command")

    shorten_parser = subcommand_parsers.add_parser(
        "shorten",
        help="Shorten a long URL into a short code"
    )
    shorten_parser.add_argument(
        "url",
        help="The URL to shorten (must start with http:// or https://)"
    )
    shorten_parser.add_argument(
        "--alias",
        default=None,
        help="Optional custom alias to use instead of an auto-generated code"
    )

    resolve_parser = subcommand_parsers.add_parser(
        "resolve",
        help="Look up the original URL for a given short code"
    )
    resolve_parser.add_argument(
        "code",
        help="The short code to look up"
    )

    list_parser = subcommand_parsers.add_parser(
        "list",
        help="Show all shortened URLs"
    )

    delete_parser = subcommand_parsers.add_parser(
        "delete",
        help="Delete a shortened URL by its short code"
    )
    delete_parser.add_argument(
        "code",
        help="The short code to delete"
    )

    return parser


def main():
    setup_database()

    argument_parser = build_argument_parser()
    parsed_args = argument_parser.parse_args()

    if parsed_args.command is None:
        argument_parser.print_help()
        sys.exit(0)

    if parsed_args.command == "shorten":
        handle_shorten_command(parsed_args.url, parsed_args.alias)


if __name__ == "__main__":
    main()
