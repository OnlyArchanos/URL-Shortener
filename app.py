import time
import html
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
    check_if_url_is_expired,
    create_new_user,
    authenticate_user_login,
    find_user_by_api_key,
    get_top_clicked_urls
)


application = Flask(__name__)

request_timestamps_by_ip = {}
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60


def check_rate_limit(client_ip_address):
    current_time = time.time()

    if client_ip_address not in request_timestamps_by_ip:
        request_timestamps_by_ip[client_ip_address] = []

    window_start_time = current_time - RATE_LIMIT_WINDOW_SECONDS
    recent_timestamps = [
        ts for ts in request_timestamps_by_ip[client_ip_address]
        if ts > window_start_time
    ]

    request_timestamps_by_ip[client_ip_address] = recent_timestamps

    if len(recent_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    recent_timestamps.append(current_time)
    return True


def get_authenticated_user():
    api_key_value = request.headers.get("X-API-Key")

    if api_key_value is None:
        return None, (jsonify({"error": "Missing X-API-Key header"}), 401)

    database_connection = get_database_connection()
    user_row = find_user_by_api_key(database_connection, api_key_value)
    database_connection.close()

    if user_row is None:
        return None, (jsonify({"error": "Invalid API key"}), 401)

    return user_row, None


@application.route("/register", methods=["POST"])
def handle_register_request():
    request_body = request.get_json()

    if request_body is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = request_body.get("username")
    password = request_body.get("password")

    if username is None or password is None:
        return jsonify({"error": "Missing 'username' or 'password' field"}), 400

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    database_connection = get_database_connection()
    new_api_key, error_message = create_new_user(database_connection, username, password)

    if error_message is not None:
        database_connection.close()
        return jsonify({"error": error_message}), 409

    database_connection.commit()
    database_connection.close()

    return jsonify({
        "message": f"User '{username}' created successfully",
        "api_key": new_api_key
    }), 201


@application.route("/login", methods=["POST"])
def handle_login_request():
    request_body = request.get_json()

    if request_body is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = request_body.get("username")
    password = request_body.get("password")

    if username is None or password is None:
        return jsonify({"error": "Missing 'username' or 'password' field"}), 400

    database_connection = get_database_connection()
    api_key = authenticate_user_login(database_connection, username, password)
    database_connection.close()

    if api_key is None:
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"api_key": api_key})


@application.route("/shorten", methods=["POST"])
def handle_shorten_request():
    if not check_rate_limit(request.remote_addr):
        return jsonify({"error": "Rate limit exceeded. Try again in a minute."}), 429

    authenticated_user, auth_error = get_authenticated_user()
    if auth_error is not None:
        return auth_error

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

    save_url_to_database(
        database_connection, chosen_short_code, url_to_shorten, is_custom,
        ttl_seconds=ttl_seconds, user_id=authenticated_user["id"]
    )

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
    authenticated_user, auth_error = get_authenticated_user()
    if auth_error is not None:
        return auth_error

    database_connection = get_database_connection()

    url_row = find_url_by_short_code(database_connection, short_code)

    if url_row is None:
        database_connection.close()
        return jsonify({"error": f"No URL found for '{short_code}'"}), 404

    if url_row["user_id"] != authenticated_user["id"]:
        database_connection.close()
        return jsonify({"error": "You don't have access to this URL"}), 403

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
    authenticated_user, auth_error = get_authenticated_user()
    if auth_error is not None:
        return auth_error

    database_connection = get_database_connection()

    url_row = find_url_by_short_code(database_connection, short_code)

    if url_row is None:
        database_connection.close()
        return jsonify({"error": f"No URL found for '{short_code}'"}), 404

    if url_row["user_id"] != authenticated_user["id"]:
        database_connection.close()
        return jsonify({"error": "You don't have access to this URL"}), 403

    deleted_original_url = url_row["original_url"]

    delete_url_from_database(database_connection, short_code)
    database_connection.commit()
    database_connection.close()

    return jsonify({
        "message": "Deleted successfully",
        "short_code": short_code,
        "original_url": deleted_original_url
    })


@application.route("/analytics")
def handle_analytics_request():
    authenticated_user, auth_error = get_authenticated_user()
    if auth_error is not None:
        return auth_error

    database_connection = get_database_connection()
    top_urls = get_top_clicked_urls(database_connection, authenticated_user["id"], 5)
    database_connection.close()

    username = html.escape(authenticated_user["username"])

    table_rows = ""
    if len(top_urls) == 0:
        table_rows = '<tr><td colspan="4" style="text-align:center;padding:20px;">No URLs yet</td></tr>'
    else:
        for url_row in top_urls:
            safe_code = html.escape(str(url_row["short_code"]))
            safe_url = html.escape(str(url_row["original_url"]))
            table_rows += (
                f"<tr>"
                f"<td>{safe_code}</td>"
                f"<td>{safe_url}</td>"
                f"<td>{url_row['click_count']}</td>"
                f"<td>{url_row['created_at']}</td>"
                f"</tr>"
            )

    page_html = (
        "<!DOCTYPE html>"
        "<html><head><title>Analytics</title></head>"
        "<body style='font-family:sans-serif;max-width:800px;margin:40px auto;padding:0 20px;'>"
        f"<h1>Analytics for {username}</h1>"
        "<table style='width:100%;border-collapse:collapse;'>"
        "<tr style='border-bottom:2px solid #333;'>"
        "<th style='text-align:left;padding:8px;'>Short Code</th>"
        "<th style='text-align:left;padding:8px;'>Original URL</th>"
        "<th style='text-align:left;padding:8px;'>Clicks</th>"
        "<th style='text-align:left;padding:8px;'>Created</th>"
        "</tr>"
        f"{table_rows}"
        "</table>"
        "</body></html>"
    )

    return page_html


if __name__ == "__main__":
    setup_database()
    application.run(debug=True, port=5000)
