import os
from flask import Flask, request, jsonify, redirect
from database import (
    setup_database,
    get_database_connection,
    get_next_short_code,
    check_if_url_is_valid,
    validate_custom_alias,
    save_url_to_database,
    find_url_by_short_code,
    delete_url_from_database,
    increment_click_count,
    check_if_url_is_expired
)


application = Flask(__name__)


@application.route("/shorten", methods=["POST"])
def handle_shorten_request():
    request_body = request.get_json()

    if request_body is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    url_to_shorten = request_body.get("url")

    if url_to_shorten is None:
        return jsonify({"error": "Missing 'url' field"}), 400

    if not check_if_url_is_valid(url_to_shorten):
        return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400

    custom_alias = request_body.get("alias")
    ttl_seconds = request_body.get("ttl_seconds")

    database_connection = get_database_connection()

    if custom_alias is not None:
        alias_error_message = validate_custom_alias(custom_alias, database_connection)

        if alias_error_message is not None:
            database_connection.close()
            return jsonify({"error": alias_error_message}), 409

        chosen_short_code = custom_alias
        is_custom = True
    else:
        chosen_short_code = get_next_short_code(database_connection)
        is_custom = False

    save_url_to_database(database_connection, chosen_short_code, url_to_shorten, is_custom, ttl_seconds=ttl_seconds)

    database_connection.commit()
    database_connection.close()

    short_url = request.host_url + chosen_short_code

    response_data = {
        "short_code": chosen_short_code,
        "short_url": short_url,
        "original_url": url_to_shorten
    }

    if ttl_seconds is not None:
        response_data["ttl_seconds"] = ttl_seconds

    return jsonify(response_data), 201


@application.route("/<short_code>")
def handle_redirect_request(short_code):
    database_connection = get_database_connection()

    url_row = find_url_by_short_code(database_connection, short_code)

    if url_row is None:
        database_connection.close()
        return jsonify({"error": f"No URL found for '{short_code}'"}), 404

    if check_if_url_is_expired(url_row):
        delete_url_from_database(database_connection, short_code)
        database_connection.commit()
        database_connection.close()
        return jsonify({"error": "This link has expired"}), 410

    increment_click_count(database_connection, short_code)
    database_connection.commit()

    original_url = url_row["original_url"]
    database_connection.close()

    return redirect(original_url, code=302)


@application.route("/stats/<short_code>")
def handle_stats_request(short_code):
    database_connection = get_database_connection()

    url_row = find_url_by_short_code(database_connection, short_code)

    if url_row is None:
        database_connection.close()
        return jsonify({"error": f"No URL found for '{short_code}'"}), 404

    if check_if_url_is_expired(url_row):
        delete_url_from_database(database_connection, short_code)
        database_connection.commit()
        database_connection.close()
        return jsonify({"error": "This link has expired"}), 410

    database_connection.close()

    return jsonify({
        "short_code": short_code,
        "original_url": url_row["original_url"],
        "created_at": url_row["created_at"],
        "click_count": url_row["click_count"],
        "is_custom": bool(url_row["is_custom"])
    })


@application.route("/<short_code>", methods=["DELETE"])
def handle_delete_request(short_code):
    expected_api_key = os.environ.get("API_KEY")
    provided_api_key = request.headers.get("X-API-Key")

    if expected_api_key is not None and provided_api_key != expected_api_key:
        return jsonify({"error": "Invalid or missing API key"}), 401

    database_connection = get_database_connection()

    url_row = find_url_by_short_code(database_connection, short_code)

    if url_row is None:
        database_connection.close()
        return jsonify({"error": f"No URL found for '{short_code}'"}), 404

    deleted_original_url = url_row["original_url"]

    delete_url_from_database(database_connection, short_code)
    database_connection.commit()
    database_connection.close()

    return jsonify({
        "message": "Deleted successfully",
        "short_code": short_code,
        "original_url": deleted_original_url
    })


if __name__ == "__main__":
    setup_database()
    application.run(debug=True, port=5000)
