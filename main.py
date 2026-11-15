import json
import secrets
import string
import uuid
from datetime import datetime, time, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from redis.exceptions import RedisError
from sqlalchemy import func, literal_column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from cache import get_redis
from database import get_db
from models import ClickEvent, Link, User

app = FastAPI()

ALPHABET = string.ascii_letters + string.digits
CACHE_TTL_SECONDS = 3600  # 1 hour


def cache_key(short_code: str) -> str:
    return f"link:{short_code}"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ShortenRequest(BaseModel):
    original_url: HttpUrl


def generate_code(length: int = 7) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    db.refresh(user)
    return {"id": str(user.id), "email": user.email, "created_at": user.created_at}


@app.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@app.post("/shorten", status_code=201)
def shorten(
    body: ShortenRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    original_url = str(body.original_url)

    for _ in range(5):
        code = generate_code()
        db.add(Link(user_id=user.id, short_code=code, original_url=original_url))
        try:
            db.commit()
            return {"short_code": code, "original_url": original_url}
        except IntegrityError:
            db.rollback()

    raise HTTPException(status_code=500, detail="Could not generate a unique code")


@app.get("/links")
def my_links(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    links = (
        db.query(Link)
        .filter_by(user_id=user.id)
        .order_by(Link.created_at.desc())
        .all()
    )
    return [
        {
            "short_code": link.short_code,
            "original_url": link.original_url,
            "created_at": link.created_at,
            "is_active": link.is_active,
        }
        for link in links
    ]


@app.get("/stats/{short_code}")
def stats(
    short_code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Only the owner can see a link's stats
    link = db.query(Link).filter_by(short_code=short_code, user_id=user.id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    total_clicks = (
        db.query(func.count(ClickEvent.id))
        .filter(ClickEvent.link_id == link.id)
        .scalar()
    )

    # Last 7 days, including today (UTC)
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=6)
    window_start = datetime.combine(first_day, time.min, tzinfo=timezone.utc)

    day = func.date(func.timezone(literal_column("'UTC'"), ClickEvent.clicked_at))
    rows = (
        db.query(day, func.count(ClickEvent.id))
        .filter(ClickEvent.link_id == link.id, ClickEvent.clicked_at >= window_start)
        .group_by(day)
        .all()
    )
    counts = {str(d): c for d, c in rows}
    clicks_per_day = []
    for i in range(7):
        d = str(first_day + timedelta(days=i))
        clicks_per_day.append({"date": d, "clicks": counts.get(d, 0)})

    referrer_rows = (
        db.query(ClickEvent.referrer, func.count(ClickEvent.id))
        .filter(ClickEvent.link_id == link.id, ClickEvent.referrer.isnot(None))
        .group_by(ClickEvent.referrer)
        .order_by(func.count(ClickEvent.id).desc())
        .limit(5)
        .all()
    )

    return {
        "short_code": link.short_code,
        "original_url": link.original_url,
        "total_clicks": total_clicks,
        "clicks_per_day": clicks_per_day,
        "top_referrers": [{"referrer": r, "clicks": c} for r, c in referrer_rows],
    }


# This must stay LAST: it matches any path, so anything below it would be swallowed
@app.get("/{short_code}")
def redirect(
    short_code: str,
    request: Request,
    db: Session = Depends(get_db),
    cache=Depends(get_redis),
):
    link_id = None
    target = None

    # 1. Check Redis first
    try:
        cached = cache.get(cache_key(short_code))
    except RedisError:
        cached = None  # Redis down: fall back to Postgres

    if cached:
        data = json.loads(cached)
        link_id, target = data["link_id"], data["original_url"]
    else:
        # 2. Cache miss: ask Postgres, then save to Redis for 1 hour
        link = db.query(Link).filter_by(short_code=short_code, is_active=True).first()
        if link is None:
            raise HTTPException(status_code=404, detail="Link not found")
        link_id, target = str(link.id), link.original_url
        try:
            cache.set(
                cache_key(short_code),
                json.dumps({"link_id": link_id, "original_url": target}),
                ex=CACHE_TTL_SECONDS,
            )
        except RedisError:
            pass

    # Every redirect is still recorded as a click, cached or not
    db.add(ClickEvent(link_id=uuid.UUID(link_id), referrer=request.headers.get("referer")))
    db.commit()
    return RedirectResponse(url=target, status_code=302)