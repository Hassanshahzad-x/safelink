import base64
import secrets
import os
from flask import Flask, request
from flask_cors import CORS
from datetime import datetime, timedelta
from urllib.parse import urlparse
from shared.datastore import store_link
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
BACKEND_BASE_URL = os.getenv("RESOLVER_SERVICE_URL")


def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and parsed.netloc
    except Exception:
        return False


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json()

    original_url = data.get("url")
    ttl_hours = data.get("ttl_hours", 24)
    max_clicks = data.get("max_clicks", 1)

    try:
        ttl_hours = int(ttl_hours)
        if ttl_hours <= 0:
            return {"error": "Hours must be > 0"}, 400
    except Exception as e:
        return {"error": "Invalid 'hours'"}, 400

    try:
        max_clicks = int(max_clicks)
        if max_clicks <= 0:
            return {"error": "Max clicks must be > 0"}, 400
    except Exception as e:
        print("Invalid max_clicks:", e)
        return {"error": "Invalid 'max clicks'"}, 400

    if not original_url or not is_valid_url(original_url):
        return {"error": "Invalid or missing URL"}, 400

    short_id = (
        base64.urlsafe_b64encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")
    )

    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

    store_link(short_id, original_url, expires_at, max_clicks)

    return {"short_url": f"{BACKEND_BASE_URL}/r/{short_id}"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
