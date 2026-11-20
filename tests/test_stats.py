from datetime import datetime, timezone

from conftest import login_headers

from worker import process_batch

URL = "https://example.com/very/long/link"


def make_link(client, headers):
    r = client.post("/shorten", json={"original_url": URL}, headers=headers)
    return r.json()["short_code"]


def test_stats_requires_token(client):
    assert client.get("/stats/abc1234").status_code == 401


def test_stats_unknown_code_returns_404(client, auth_headers):
    assert client.get("/stats/doesnotexist", headers=auth_headers).status_code == 404


def test_stats_for_someone_elses_link_returns_404(client):
    mine = login_headers(client, "me@example.com")
    theirs = login_headers(client, "other@example.com")
    code = make_link(client, mine)
    assert client.get(f"/stats/{code}", headers=theirs).status_code == 404


def test_stats_totals_days_and_referrers(client, db, redis_client, auth_headers):
    code = make_link(client, auth_headers)

    twitter = {"referer": "https://twitter.com/"}
    client.get(f"/{code}", headers=twitter, follow_redirects=False)
    client.get(f"/{code}", headers=twitter, follow_redirects=False)
    client.get(f"/{code}", headers={"referer": "https://google.com/"}, follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)  # direct visit, no referrer

    process_batch(redis_client, db, timeout=1)  # the worker saves the queued clicks

    r = client.get(f"/stats/{code}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()

    assert data["total_clicks"] == 4

    assert len(data["clicks_per_day"]) == 7
    today = datetime.now(timezone.utc).date().isoformat()
    assert data["clicks_per_day"][-1] == {"date": today, "clicks": 4}

    assert data["top_referrers"][0] == {"referrer": "https://twitter.com/", "clicks": 2}
    assert len(data["top_referrers"]) == 2  # direct visits are not a referrer
    

def test_stats_for_link_with_no_clicks(client, auth_headers):
    code = make_link(client, auth_headers)
    data = client.get(f"/stats/{code}", headers=auth_headers).json()
    assert data["total_clicks"] == 0
    assert all(day["clicks"] == 0 for day in data["clicks_per_day"])
    assert data["top_referrers"] == []