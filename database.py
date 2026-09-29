import sqlite3
import os
import string
from datetime import datetime, timedelta
from urllib.parse import urlparse


BASE62_CHARACTERS = string.digits + string.ascii_lowercase + string.ascii_uppercase

STARTING_COUNTER_VALUE = 100000

DATABASE_FILENAME = "urls.db"

RESERVED_ROUTE_NAMES = {"shorten", "register", "login", "stats", "analytics"}


def get_database_path():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    database_path = os.path.join(script_directory, DATABASE_FILENAME)
    return database_path


def get_database_connection():
    database_path = get_database_path()
    database_connection = sqlite3.connect(database_path)
    database_connection.row_factory = sqlite3.Row
    return database_connection


def get_existing_column_names_for_urls(database_cursor):
    database_cursor.execute("PRAGMA table_info(urls)")
    all_columns = database_cursor.fetchall()
    column_names = [column_info[1] for column_info in all_columns]
    return column_names


def setup_database():
    database_connection = get_database_connection()
    database_cursor = database_connection.cursor()

    database_cursor.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_custom INTEGER NOT NULL DEFAULT 0,
            click_count INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT,
            user_id INTEGER
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

    database_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    existing_url_columns = get_existing_column_names_for_urls(database_cursor)

    if "click_count" not in existing_url_columns:
        database_cursor.execute(
            "ALTER TABLE urls ADD COLUMN click_count INTEGER NOT NULL DEFAULT 0"
        )

    if "expires_at" not in existing_url_columns:
        database_cursor.execute("ALTER TABLE urls ADD COLUMN expires_at TEXT")

    if "user_id" not in existing_url_columns:
        database_cursor.execute("ALTER TABLE urls ADD COLUMN user_id INTEGER")

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

    if alias_text.lower() in RESERVED_ROUTE_NAMES:
        return f"'{alias_text}' is a reserved name and cannot be used as an alias."

    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "SELECT id FROM urls WHERE short_code = ?",
        (alias_text,)
    )
    existing_row = database_cursor.fetchone()

    if existing_row is not None:
        return f"The alias '{alias_text}' is already taken. Please choose a different one."

    return None


def save_url_to_database(database_connection, short_code, original_url, is_custom_alias, ttl_seconds=None, user_id=None):
    database_cursor = database_connection.cursor()

    creation_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    custom_flag = 1 if is_custom_alias else 0

    expiry_timestamp = None
    if ttl_seconds is not None:
        expiry_datetime = datetime.now() + timedelta(seconds=int(ttl_seconds))
        expiry_timestamp = expiry_datetime.strftime("%Y-%m-%d %H:%M:%S")

    database_cursor.execute(
        "INSERT INTO urls (short_code, original_url, created_at, is_custom, expires_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (short_code, original_url, creation_timestamp, custom_flag, expiry_timestamp, user_id)
    )


def find_url_by_short_code(database_connection, short_code):
    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "SELECT short_code, original_url, created_at, is_custom, click_count, expires_at, user_id "
        "FROM urls WHERE short_code = ?",
        (short_code,)
    )
    found_row = database_cursor.fetchone()
    return found_row


def delete_url_from_database(database_connection, short_code):
    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "DELETE FROM urls WHERE short_code = ?",
        (short_code,)
    )


def increment_click_count(database_connection, short_code):
    database_cursor = database_connection.cursor()

    database_cursor.execute(
        "UPDATE urls SET click_count = click_count + 1 WHERE short_code = ?",
        (short_code,)
    )


def get_all_urls(database_connection, user_id=None):
    database_cursor = database_connection.cursor()

    if user_id is None:
        database_cursor.execute(
            "SELECT short_code, original_url, created_at, is_custom, click_count "
            "FROM urls ORDER BY created_at DESC"
        )
    else:
        database_cursor.execute(
            "SELECT short_code, original_url, created_at, is_custom, click_count "
            "FROM urls WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )

    all_url_rows = database_cursor.fetchall()
    return all_url_rows


def check_if_url_is_expired(url_row):
    expiry_timestamp = url_row["expires_at"]

    if expiry_timestamp is None:
        return False

    expiry_datetime = datetime.strptime(expiry_timestamp, "%Y-%m-%d %H:%M:%S")
    current_datetime = datetime.now()

    return current_datetime > expiry_datetime

