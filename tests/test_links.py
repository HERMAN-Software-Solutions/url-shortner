from conftest import login_headers
from models import ClickEvent, Link

URL = "https://example.com/very/long/link"


def test_shorten_click_and_redirect(client, db, auth_headers):
    r = client.post("/shorten", json={"original_url": URL}, headers=auth_headers)
    assert r.status_code == 201
    data = r.json()
    assert len(data["short_code"]) == 7
    assert data["original_url"] == URL

    r2 = client.get(f"/{data['short_code']}", follow_redirects=False)
    assert r2.status_code == 302
    assert r2.headers["location"] == URL
    assert db.query(ClickEvent).count() == 1


def test_unknown_code_returns_404(client, db):
    r = client.get("/doesnotexist", follow_redirects=False)
    assert r.status_code == 404
    assert db.query(ClickEvent).count() == 0


def test_inactive_link_returns_404(client, db, auth_headers):
    code = client.post(
        "/shorten", json={"original_url": URL}, headers=auth_headers
    ).json()["short_code"]
    db.query(Link).filter_by(short_code=code).update({"is_active": False})
    db.commit()

    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 404
    assert db.query(ClickEvent).count() == 0


def test_invalid_url_is_rejected(client, auth_headers):
    r = client.post("/shorten", json={"original_url": "not a url"}, headers=auth_headers)
    assert r.status_code == 422


def test_shorten_without_token_returns_401(client):
    r = client.post("/shorten", json={"original_url": URL})
    assert r.status_code == 401


def test_shorten_with_bad_token_returns_401(client):
    r = client.post(
        "/shorten",
        json={"original_url": URL},
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert r.status_code == 401


def test_links_requires_token(client):
    assert client.get("/links").status_code == 401


def test_links_only_returns_my_links(client):
    mine = login_headers(client, "me@example.com")
    theirs = login_headers(client, "other@example.com")

    client.post("/shorten", json={"original_url": URL}, headers=mine)
    client.post("/shorten", json={"original_url": URL}, headers=mine)
    client.post("/shorten", json={"original_url": URL}, headers=theirs)

    assert len(client.get("/links", headers=mine).json()) == 2
    assert len(client.get("/links", headers=theirs).json()) == 1