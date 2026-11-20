import json
import logging
import signal
import time
import uuid
from datetime import datetime

import redis
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from cache import CLICK_QUEUE, REDIS_URL
from database import SessionLocal
from models import ClickEvent

BATCH_SIZE = 100
BLOCK_SECONDS = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

running = True


def stop(signum, frame):
    global running
    running = False


def parse_event(raw):
    """Turn one JSON string from the queue into a ClickEvent, or None if invalid."""
    try:
        data = json.loads(raw)
        return ClickEvent(
            link_id=uuid.UUID(data["link_id"]),
            referrer=data.get("referrer"),
            clicked_at=datetime.fromisoformat(data["clicked_at"]),
        )
    except (ValueError, KeyError, TypeError):
        log.warning("Dropping invalid event: %r", raw)
        return None


def save_one_by_one(db, raws):
    """Used when a batch fails because of one bad event (e.g. the link no longer exists)."""
    saved = 0
    for raw in raws:
        try:
            db.add(parse_event(raw))
            db.commit()
            saved += 1
        except IntegrityError:
            db.rollback()
            log.warning("Dropping event that breaks a constraint: %r", raw)
    return saved


def process_batch(redis_client, db, timeout=BLOCK_SECONDS, batch_size=BATCH_SIZE):
    """Wait for one event, grab up to batch_size more, save them. Returns how many were saved."""
    first = redis_client.blpop(CLICK_QUEUE, timeout=timeout)  # sleeps while the queue is empty
    if first is None:
        return 0

    raw_events = [first[1]]
    while len(raw_events) < batch_size:
        raw = redis_client.lpop(CLICK_QUEUE)
        if raw is None:
            break
        raw_events.append(raw)

    valid = [raw for raw in raw_events if parse_event(raw) is not None]

    try:
        db.add_all([parse_event(raw) for raw in valid])
        db.commit()
        return len(valid)
    except IntegrityError:
        db.rollback()
        return save_one_by_one(db, valid)
    except SQLAlchemyError:
        db.rollback()
        redis_client.rpush(CLICK_QUEUE, *valid)  # database problem: put the events back
        raise


def main():
    # No socket_timeout here: BLPOP waits up to 5 seconds, longer than the API client allows
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("Worker started, waiting for clicks on %s", CLICK_QUEUE)

    while running:
        db = SessionLocal()
        try:
            saved = process_batch(client, db)
            if saved:
                log.info("Saved %d click(s) to Postgres", saved)
        except (RedisError, SQLAlchemyError) as exc:
            log.error("Worker error: %s. Retrying in 5 seconds", exc)
            time.sleep(5)
        finally:
            db.close()

    log.info("Worker stopped")


if __name__ == "__main__":
    main()