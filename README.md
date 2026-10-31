# URL Shortener with Analytics

Week 2: PostgreSQL + core endpoints (`POST /shorten`, `GET /{short_code}`).

## Setup
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Create databases `shortener` and `shortener_test` in Postgres.
4. Create `.env` with `DATABASE_URL` and `TEST_DATABASE_URL`.
5. `alembic upgrade head`
6. `python seed.py` (creates the dummy user)
7. `uvicorn main:app --reload`

## Tests
`pytest -v`
