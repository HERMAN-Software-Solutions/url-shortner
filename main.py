import secrets
import string

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import ClickEvent, Link, User

app = FastAPI()

ALPHABET = string.ascii_letters + string.digits
DUMMY_EMAIL = "dummy@example.com"


class ShortenRequest(BaseModel):
    original_url: HttpUrl


def generate_code(length: int = 7) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/shorten", status_code=201)
def shorten(body: ShortenRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=DUMMY_EMAIL).first()
    if user is None:
        raise HTTPException(status_code=500, detail="Dummy user missing. Run seed.py")

    original_url = str(body.original_url)

    # Retry a few times in the rare case two random codes collide
    for _ in range(5):
        code = generate_code()
        db.add(Link(user_id=user.id, short_code=code, original_url=original_url))
        try:
            db.commit()
            return {"short_code": code, "original_url": original_url}
        except IntegrityError:
            db.rollback()

    raise HTTPException(status_code=500, detail="Could not generate a unique code")


@app.get("/{short_code}")
def redirect(short_code: str, request: Request, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(short_code=short_code, is_active=True).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    target = link.original_url
    db.add(ClickEvent(link_id=link.id, referrer=request.headers.get("referer")))
    db.commit()
    return RedirectResponse(url=target, status_code=302)