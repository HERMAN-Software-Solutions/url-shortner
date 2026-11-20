import json
import uuid
from datetime import datetime, timezone

from cache import CLICK_QUEUE
from models import ClickEvent, Link
from worker import process_batch

URL = "https://example.com/very/long/link"


def make_link(client, headers):
    return client.post("/shorten", json={"original_url": URL}, headers=headers).json()["short_code"]


def event_for(link_id, referrer=None):
    return json.dumps(
        {
            "link_id": str(link_id),
            "referrer": referrer,
            "clicked_at": datetime.now(timezone.utc).isoformat(),
        }
    )


# --- The redirect side ---

def test_redirect_pushes_click_to_queue_and_not_to_postgres(client, db, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    link = db.query(Link).filter_by(short_code=code).one()

    r = client.get(f"/{code}", headers={"referer": "https://twitter.com/"}, follow_redirects=False)
    assert r.status_code == 302

    assert db.query(ClickEvent).count() == 0
    assert redis_client.llen(CLICK_QUEUE) == 1
    event = json.loads(redis_client.lpop(CLICK_QUEUE))
    assert event["link_id"] == str(link.id)
    assert event["referrer"] == "https://twitter.com/"
    assert "clicked_at" in event


# --- The worker side ---

def test_worker_saves_one_queued_event(client, db, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    link = db.query(Link).filter_by(short_code=code).one()
    redis_client.rpush(CLICK_QUEUE, event_for(link.id, "https://twitter.com/"))

    saved = process_batch(redis_client, db, timeout=1)

    assert saved == 1
    assert redis_client.llen(CLICK_QUEUE) == 0
    click = db.query(ClickEvent).one()
    assert click.link_id == link.id
    assert click.referrer == "https://twitter.com/"


def test_worker_saves_a_batch(client, db, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    link = db.query(Link).filter_by(short_code=code).one()
    for _ in range(5):
        redis_client.rpush(CLICK_QUEUE, event_for(link.id))

    assert process_batch(redis_client, db, timeout=1) == 5
    assert db.query(ClickEvent).count() == 5


def test_worker_respects_batch_size(client, db, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    link = db.query(Link).filter_by(short_code=code).one()
    for _ in range(5):
        redis_client.rpush(CLICK_QUEUE, event_for(link.id))

    assert process_batch(redis_client, db, timeout=1, batch_size=2) == 2
    assert redis_client.llen(CLICK_QUEUE) == 3


def test_worker_returns_zero_when_queue_is_empty(client, db, redis_client):
    assert process_batch(redis_client, db, timeout=1) == 0
    assert db.query(ClickEvent).count() == 0


def test_worker_skips_invalid_events(client, db, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    link = db.query(Link).filter_by(short_code=code).one()
    redis_client.rpush(CLICK_QUEUE, "this is not json")
    redis_client.rpush(CLICK_QUEUE, event_for(link.id))

    assert process_batch(redis_client, db, timeout=1) == 1
    assert db.query(ClickEvent).count() == 1
    assert redis_client.llen(CLICK_QUEUE) == 0


def test_worker_drops_event_for_a_missing_link_but_saves_the_rest(client, db, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    link = db.query(Link).filter_by(short_code=code).one()
    redis_client.rpush(CLICK_QUEUE, event_for(uuid.uuid4()))  # link does not exist
    redis_client.rpush(CLICK_QUEUE, event_for(link.id))

    assert process_batch(redis_client, db, timeout=1) == 1
    assert db.query(ClickEvent).count() == 1