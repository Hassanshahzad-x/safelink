from google.cloud import datastore
from datetime import datetime, timezone

client = datastore.Client()


def store_link(short_id, original_url, expires_at, max_clicks):
    key = client.key("Links", short_id)
    entity = datastore.Entity(key=key)

    entity.update(
        {
            "original_url": original_url,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "max_clicks": max_clicks,
            "clicks": 0,
        }
    )

    client.put(entity)


def fetch_link(short_id):
    key = client.key("Links", short_id)
    entity = client.get(key)

    if not entity:
        return None

    now = datetime.now(timezone.utc)
    if entity["expires_at"] < now or entity["clicks"] >= entity["max_clicks"]:
        return None

    return dict(entity)


def increment_clicks(short_id):
    key = client.key("Links", short_id)
    entity = client.get(key)

    if entity:
        entity["clicks"] += 1
        client.put(entity)
