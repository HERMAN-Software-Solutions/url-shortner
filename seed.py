from database import SessionLocal
from models import User

db = SessionLocal()

existing = db.query(User).filter_by(email="dummy@example.com").first()
if existing is None:
    db.add(User(email="dummy@example.com", password_hash="not-a-real-hash"))
    db.commit()
    print("dummy user created")
else:
    print("dummy user already exists")

db.close()