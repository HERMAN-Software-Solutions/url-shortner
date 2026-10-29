import uuid

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey, Index, String, Text, func, text)
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Link(Base):
    __tablename__ = "links"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    short_code = Column(String(20), unique=True, nullable=False)
    original_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, server_default=text("true"), nullable=False)    
    
class ClickEvent(Base):
    __tablename__ = "click_events"

    id = Column(BigInteger, primary_key=True)
    link_id = Column(UUID, ForeignKey("links.id"), nullable=False)    
    clicked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    referrer = Column(Text, nullable=True)
    
    __table_args__ = (Index("ix_click_events_link_id_clicked_at", "link_id", "clicked_at"),)