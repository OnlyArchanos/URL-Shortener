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


if __name__ == "__main__":
    setup_database()

    database_connection = get_database_connection()
    first_code = get_next_short_code(database_connection)
    database_connection.commit()
    database_connection.close()

    print(f"First generated code: {first_code}")
