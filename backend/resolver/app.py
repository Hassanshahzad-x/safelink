from flask import Flask, redirect
from flask_cors import CORS
from shared.datastore import fetch_link, increment_clicks

app = Flask(__name__)
CORS(app)


@app.route("/r/<short_id>")
def resolve(short_id):
    record = fetch_link(short_id)

    if not record:
        return "Link expired or not found", 410

    increment_clicks(short_id)
    return redirect(record["original_url"], code=302)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
