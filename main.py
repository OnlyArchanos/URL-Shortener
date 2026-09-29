import sys
import argparse
from database import (
    setup_database,
    get_database_connection,
    get_next_short_code,
    check_if_url_is_valid,
    validate_custom_alias,
    save_url_to_database,
    find_url_by_short_code,
    delete_url_from_database,
    get_all_urls
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


def handle_resolve_command(short_code_to_find):
    database_connection = get_database_connection()

    found_row = find_url_by_short_code(database_connection, short_code_to_find)
    database_connection.close()

    if found_row is None:
        print(
            f"Error: No URL found for short code '{short_code_to_find}'.",
            file=sys.stderr
        )
        sys.exit(1)

    url_type_label = "Custom Alias" if found_row["is_custom"] else "Auto-Generated"

    print(f"\nResolved successfully!")
    print(f"  Short Code    : {short_code_to_find}")
    print(f"  Original URL  : {found_row['original_url']}")
    print(f"  Created At    : {found_row['created_at']}")
    print(f"  Type          : {url_type_label}")
    print()


URL_DISPLAY_MAX_LENGTH = 60


def format_list_table_header(code_column_width, url_column_width):
    date_column_width = 19
    type_column_width = 6

    header_text = (
        f"  {'Short Code':<{code_column_width}}"
        f"  {'Original URL':<{url_column_width}}"
        f"  {'Created At':<{date_column_width}}"
        f"  {'Type':<{type_column_width}}"
    )

    separator_text = (
        f"  {'-' * code_column_width}"
        f"  {'-' * url_column_width}"
        f"  {'-' * date_column_width}"
        f"  {'-' * type_column_width}"
    )

    return header_text + "\n" + separator_text


def format_list_table_row(url_row, code_column_width, url_column_width):
    display_url = url_row["original_url"]
    if len(display_url) > URL_DISPLAY_MAX_LENGTH:
        display_url = display_url[:URL_DISPLAY_MAX_LENGTH - 3] + "..."

    type_label = "Custom" if url_row["is_custom"] else "Auto"

    formatted_line = (
        f"  {url_row['short_code']:<{code_column_width}}"
        f"  {display_url:<{url_column_width}}"
        f"  {url_row['created_at']:<19}"
        f"  {type_label}"
    )

    return formatted_line


def handle_list_command():
    database_connection = get_database_connection()

    all_url_rows = get_all_urls(database_connection)
    database_connection.close()

    if len(all_url_rows) == 0:
        print("\nNo shortened URLs found. Use 'shorten' to create one.\n")
        return

    longest_code = max(len(url_row["short_code"]) for url_row in all_url_rows)
    code_column_width = max(len("Short Code"), longest_code)

    longest_url = max(len(url_row["original_url"]) for url_row in all_url_rows)
    url_column_width = max(len("Original URL"), min(longest_url, URL_DISPLAY_MAX_LENGTH))

    print(f"\n  Found {len(all_url_rows)} shortened URL(s):\n")
    print(format_list_table_header(code_column_width, url_column_width))

    for url_row in all_url_rows:
        print(format_list_table_row(url_row, code_column_width, url_column_width))

    print()


def handle_delete_command(short_code_to_delete):
    database_connection = get_database_connection()

    found_row = find_url_by_short_code(database_connection, short_code_to_delete)

    if found_row is None:
        print(
            f"Error: No URL found for short code '{short_code_to_delete}'.",
            file=sys.stderr
        )
        database_connection.close()
        sys.exit(1)

    deleted_original_url = found_row["original_url"]

    delete_url_from_database(database_connection, short_code_to_delete)

    database_connection.commit()
    database_connection.close()

    print(f"\nDeleted successfully!")
    print(f"  Short Code    : {short_code_to_delete}")
    print(f"  Original URL  : {deleted_original_url}")
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

    if parsed_args.command == "resolve":
        handle_resolve_command(parsed_args.code)

    if parsed_args.command == "list":
        handle_list_command()

    if parsed_args.command == "delete":
        handle_delete_command(parsed_args.code)


if __name__ == "__main__":
    main()
