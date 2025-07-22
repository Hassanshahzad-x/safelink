from google.cloud import datastore
from datetime import datetime, timezone

client = datastore.Client()


def delete_expired_links(request):
    query = client.query(kind="Links")
    now = datetime.now(timezone.utc)
    deleted = 0

    for entity in query.fetch():
        if entity["expires_at"] < now or entity["clicks"] >= entity["max_clicks"]:
            client.delete(entity.key)
            deleted += 1

    return f"{deleted} expired links deleted.", 200
