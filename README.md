# URL Shortener with Analytics

A URL shortener built with FastAPI and PostgreSQL. Users register, log in with a JWT, create short links, and list their own links. Opening a short link redirects to the original URL and records a click.

**Progress:** Week 2 (Postgres + core endpoints) and Week 3 (authentication and user-owned links) are complete.

## Setup
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Create two Postgres databases: `shortener` and `shortener_test`.
4. Create a `.env` file with:
   ```
   DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost/shortener
   TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost/shortener_test
   JWT_SECRET=<long random string>
   ```
   Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"`. Never commit `.env`.
5. `alembic upgrade head` (creates the tables)
6. `uvicorn main:app --reload`

Interactive API docs are at `http://127.0.0.1:8000/docs`. After logging in, click **Authorize** and paste the access token to call protected endpoints.

## Endpoints
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | No | Create an account (email + password, min 8 characters). Returns 409 if the email is taken. |
| POST | `/auth/login` | No | Returns a JWT access token (valid for 60 minutes). Returns 401 for wrong credentials. |
| POST | `/shorten` | JWT | Creates a 7-character base62 short code for the given `original_url`. Returns 201. |
| GET | `/links` | JWT | Lists only the logged-in user's links. |
| GET | `/{short_code}` | No | Records a click and redirects (302) to the original URL. Returns 404 if the code is missing or inactive. |

Requests to protected endpoints without a valid token return 401.

## Tests
`pytest -v`

Tests run against the `shortener_test` database. They cover registration, login, protected endpoints (401 without a token), the redirect and click recording, the 404 cases, and the rule that `/links` only returns the caller's own links.

## Design notes
- Passwords are hashed with Argon2 and never stored or returned in plain text.
- Login returns the same error for a wrong email and a wrong password.
- Redirects use 302 so browsers don't cache them and skip click counting.
- Not built yet: Redis caching, Docker, and the `/stats` endpoint.