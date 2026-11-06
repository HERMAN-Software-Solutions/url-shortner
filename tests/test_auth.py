CREDS = {"email": "angella@example.com", "password": "password123"}


def test_register_creates_user(client):
    r = client.post("/auth/register", json=CREDS)
    assert r.status_code == 201
    assert r.json()["email"] == CREDS["email"]
    assert "password" not in r.json()
    assert "password_hash" not in r.json()


def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json=CREDS)
    r = client.post("/auth/register", json=CREDS)
    assert r.status_code == 409


def test_register_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "short"})
    assert r.status_code == 422


def test_login_returns_token(client):
    client.post("/auth/register", json=CREDS)
    r = client.post("/auth/login", json=CREDS)
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json=CREDS)
    r = client.post("/auth/login", json={**CREDS, "password": "wrongpassword"})
    assert r.status_code == 401