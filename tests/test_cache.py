import json

from redis.exceptions import ConnectionError as RedisConnectionError

from cache import get_redis
from main import app
from models import ClickEvent

URL = "https://example.com/very/long/link"


def make_link(client, headers):
    r = client.post("/shorten", json={"original_url": URL}, headers=headers)
    return r.json()["short_code"]


def test_first_request_fills_cache_with_one_hour_ttl(client, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    key = f"link:{code}"
    assert redis_client.get(key) is None

    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302

    cached = json.loads(redis_client.get(key))
    assert cached["original_url"] == URL
    assert 3500 < redis_client.ttl(key) <= 3600


def test_second_request_is_served_from_cache(client, redis_client, auth_headers):
    code = make_link(client, auth_headers)
    key = f"link:{code}"
    client.get(f"/{code}", follow_redirects=False)  # fills the cache

    # Change only the cached copy. If the next redirect uses it, Redis was hit.
    data = json.loads(redis_client.get(key))
    data["original_url"] = "https://from-cache.example.com"
    redis_client.set(key, json.dumps(data), ex=3600)

    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://from-cache.example.com"


def test_cached_redirects_still_record_clicks(client, db, auth_headers):
    code = make_link(client, auth_headers)
    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)
    assert db.query(ClickEvent).count() == 2


def test_unknown_code_is_not_cached(client, redis_client):
    r = client.get("/doesnotexist", follow_redirects=False)
    assert r.status_code == 404
    assert redis_client.get("link:doesnotexist") is None


def test_redirect_still_works_when_redis_is_down(client, auth_headers):
    code = make_link(client, auth_headers)

    class BrokenRedis:
        def get(self, *args, **kwargs):
            raise RedisConnectionError("down")

        def set(self, *args, **kwargs):
            raise RedisConnectionError("down")

    app.dependency_overrides[get_redis] = lambda: BrokenRedis()
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == URL